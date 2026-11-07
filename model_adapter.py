"""Adapter for the portable Colab export. See MODEL_INTEGRATION.md."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.utils.validation import check_is_fitted
from xgboost import XGBRegressor


class ModelBundle:
    def __init__(self, metadata, preprocessor, model):
        required = {'configuration', 'model_types', 'original_numeric_features',
                    'original_categorical_features', 'numeric_columns',
                    'categorical_columns', 'input_columns', 'amenity_vocabulary',
                    'target_transform', 'prediction_inverse'}
        if not isinstance(metadata, dict) or required - metadata.keys():
            raise ValueError('Portable model metadata is missing required fields')
        config = metadata['configuration']
        if (not isinstance(config, dict)
                or config.get('representation') != 'shared_apartment_condominium'
                or config.get('subtype') is not True
                or config.get('original_type_feature') is not False):
            raise ValueError('Unsupported model configuration')
        if (metadata['target_transform'] != 'log1p'
                or metadata['prediction_inverse'] != 'expm1'):
            raise ValueError('Unsupported target transform')
        if set(metadata['model_types']) != {'house', 'apartment_condominium'}:
            raise ValueError('Unsupported prediction scope')
        for name in ('original_numeric_features', 'original_categorical_features',
                     'numeric_columns', 'categorical_columns', 'input_columns',
                     'amenity_vocabulary'):
            values = metadata[name]
            if (not isinstance(values, list)
                    or not all(isinstance(v, str) and v for v in values)
                    or len(set(values)) != len(values)):
                raise ValueError(f'Invalid {name}')
        self.metadata = metadata
        self.numeric = list(metadata['original_numeric_features'])
        self.categorical = list(metadata['categorical_columns'])
        self.columns = list(metadata['input_columns'])
        self.vocabulary = list(metadata['amenity_vocabulary'])
        amenity_columns = [f'amenity_{i:03d}' for i in range(len(self.vocabulary))]
        if (self.categorical != metadata['original_categorical_features'] + ['property_subtype']
                or self.categorical != ['property_type', 'city', 'furnishing_status', 'property_subtype']
                or metadata['numeric_columns'] != self.numeric + amenity_columns
                or len(self.columns) != len(metadata['numeric_columns']) + len(self.categorical)
                or set(self.columns) != set(metadata['numeric_columns'] + self.categorical)):
            raise ValueError('Inconsistent metadata feature columns')
        if not isinstance(preprocessor, ColumnTransformer) or not isinstance(model, XGBRegressor):
            raise ValueError('Unexpected portable model components')
        check_is_fitted(preprocessor)
        check_is_fitted(model)
        if list(preprocessor.feature_names_in_) != self.columns:
            raise ValueError('Preprocessor inputs do not match metadata column order')
        imputer = preprocessor.named_transformers_.get('number')
        encoder = preprocessor.named_transformers_.get('category')
        if (not isinstance(imputer, SimpleImputer) or imputer.strategy != 'median'
                or not imputer.add_indicator or not imputer.keep_empty_features
                or not isinstance(encoder, OneHotEncoder)
                or encoder.handle_unknown != 'ignore'):
            raise ValueError('Unexpected fitted numerical or categorical preprocessing')
        transformer_columns = {name: list(cols) for name, _, cols in preprocessor.transformers_}
        if (transformer_columns.get('number') != metadata['numeric_columns']
                or transformer_columns.get('category') != self.categorical):
            raise ValueError('Transformer columns do not match metadata')
        if set(encoder.categories_[0]) != set(metadata['model_types']):
            raise ValueError('Fitted prediction groups do not match metadata')
        if len(preprocessor.get_feature_names_out()) != model.n_features_in_:
            raise ValueError('Preprocessor output width does not match booster')
        self.preprocessor = preprocessor
        self.model = model
        # Existing API taxonomy validation; the portable metadata does not carry
        # a subtype allowlist. Subtypes remain separate from prediction groups.
        self.subtypes = {
            'house': ['house', 'townhouse', 'beach_house', 'villa'],
            'apartment': ['apartment', 'room'],
            'condominium': ['condominium', 'studio', 'loft', 'penthouse', 'condotel'],
        }
        self.type_mapping = {name: ('apartment_condominium' if name in
                            {'apartment', 'condominium'} else name)
                             for name in [*metadata['model_types'], 'apartment', 'condominium']}

    @classmethod
    def load(cls, model_dir: Path):
        model_dir = Path(model_dir)
        try:
            metadata = json.loads((model_dir / 'model_metadata.json').read_text(encoding='utf-8'))
            preprocessor = joblib.load(model_dir / 'selected_preprocessor.joblib')
            model = XGBRegressor()
            model.load_model(model_dir / 'selected_xgboost.ubj')
            return cls(metadata, preprocessor, model)
        except Exception as exc:
            raise RuntimeError(
                f'Cannot load portable model from {model_dir}: {exc}. '
                'Check the matching export files; see MODEL_INTEGRATION.md.'
            ) from exc

    def prepare(self, features):
        def category(name, default='unknown'):
            value = features.get(name)
            if value is None:
                return default
            if not isinstance(value, str):
                raise ValueError(f'{name} must be a string')
            return value.strip().lower()

        original_type = category('property_type')
        if original_type not in self.type_mapping:
            raise ValueError('Unsupported property type')
        subtype = category('property_subtype')
        if original_type in {'apartment', 'condominium'} and subtype in {'', 'unknown', 'nan'}:
            subtype = original_type
        allowed = (self.subtypes['apartment'] + self.subtypes['condominium']
                   if original_type == 'apartment_condominium' else self.subtypes[original_type])
        if subtype not in allowed and not (original_type == 'house' and subtype in {'unknown', '', 'nan'}):
            raise ValueError('property_subtype must belong to the selected property type')
        row = {col: np.nan for col in self.columns}
        row.update(property_type=self.type_mapping[original_type],
                   property_subtype=subtype, city=category('city'),
                   furnishing_status=category('furnishing_status'))
        for name in self.numeric:
            value = features.get(name)
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            if isinstance(value, (bool, list, dict)):
                raise ValueError(f'{name} must be a finite number')
            try:
                value = float(value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f'{name} must be a finite number') from exc
            if not np.isfinite(value):
                raise ValueError(f'{name} must be a finite number')
            if name == 'latitude' and not -90 <= value <= 90:
                raise ValueError('latitude must be between -90 and 90')
            if name == 'longitude' and not -180 <= value <= 180:
                raise ValueError('longitude must be between -180 and 180')
            if name not in {'latitude', 'longitude'} and value < 0:
                raise ValueError(f'{name} must be nonnegative')
            row[name] = value
        amenities = features.get('amenities_normalized')
        missing_amenities = amenities is None
        if missing_amenities:
            amenities = []
        elif isinstance(amenities, str):
            amenities = amenities.split('|')
        if not isinstance(amenities, list) or not all(isinstance(v, str) for v in amenities):
            raise ValueError('Invalid amenities format')
        selected = {v.strip() for v in amenities if v.strip()}
        row.update({f'amenity_{i:03d}': (np.nan if missing_amenities else int(term in selected))
                    for i, term in enumerate(self.vocabulary)})
        return pd.DataFrame([row], columns=self.columns)

    def predict(self, row):
        processed = self.preprocessor.transform(row)
        # The booster predicts log1p(PHP); invert once, preserving its float32
        # precision to match the notebook reference export before API rounding.
        with np.errstate(over='ignore', invalid='ignore'):
            return float(np.expm1(self.model.predict(processed)[0]))
