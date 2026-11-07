"""Portable export, reference prediction and ASGI endpoint integration tests."""
import asyncio
import copy
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from pandas.testing import assert_frame_equal

from model_adapter import ModelBundle

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = json.loads((ROOT / 'models/reference_predictions.json').read_text(encoding='utf-8'))

class Response:
    def __init__(self, messages):
        self.status_code = messages[0]['status']
        self.body = b''.join(m.get('body', b'') for m in messages[1:])
    def json(self):
        return json.loads(self.body)
class Client:
    def __init__(self, app):
        self.app = app
    def request(self, method, path, payload=None, headers=None):
        async def run():
            messages = []
            async def receive():
                return {'type': 'http.request', 'body': json.dumps(payload).encode(), 'more_body': False}
            async def send(message):
                messages.append(message)
            await self.app({'type': 'http', 'asgi': {'version': '3.0'},
                'http_version': '1.1', 'method': method, 'scheme': 'http',
                'path': path, 'raw_path': path.encode(), 'query_string': b'',
                'root_path': '', 'server': ('test', 80), 'client': ('test', 1),
                'headers': [(b'content-type', b'application/json')] + [
                    (k.lower().encode(), v.encode()) for k,v in (headers or {}).items()]}, receive, send)
            return Response(messages)
        return asyncio.run(run())
    def get(self, path):
        return self.request('GET', path)
    def post(self, path, json, headers=None):
        return self.request('POST', path, json, headers)


class ModelIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = ModelBundle.load(ROOT / 'models')
        cls.main = importlib.import_module('main')
        cls.client = Client(cls.main.app)

    def test_reference_predictions(self):
        self.assertEqual({r['request']['property_type'] for r in REFERENCES},
                         {'house', 'apartment', 'condominium'})
        for reference in REFERENCES:
            with self.subTest(kind=reference['request']['property_type']):
                actual = self.adapter.predict(self.adapter.prepare(reference['request']))
                self.assertAlmostEqual(actual, reference['expected_estimated_rent_monthly'], places=5)

    def test_reference_predictions_through_authenticated_api(self):
        with patch.dict(os.environ, {'ML_SHARED_SECRET': 'test-secret'}):
            for reference in REFERENCES:
                with self.subTest(kind=reference['request']['property_type']):
                    response = self.client.post('/predict', json=reference['request'],
                                               headers={'Authorization': 'Bearer test-secret'})
                    self.assertEqual(response.status_code, 200)
                    rent = reference['expected_estimated_rent_monthly']
                    self.assertEqual(response.json(), {
                        'estimated_rent_monthly': round(rent, 2),
                        'range_min': round(rent * .70, 2),
                        'range_max': round(rent * 1.30, 2),
                        'currency': 'PHP', 'model_version': 'development-v1'})

    def test_missing_optional_fields(self):
        for kind in ['house', 'apartment', 'condominium']:
            row = self.adapter.prepare({'property_type': kind})
            self.assertTrue(row[self.adapter.numeric].isna().all().all())
            self.assertEqual(row.at[0, 'city'], 'unknown')
            self.assertEqual(row.at[0, 'property_subtype'], 'unknown' if kind == 'house' else kind)
            rent = self.adapter.predict(row)
            self.assertTrue(np.isfinite(rent) and rent > 0)

    def test_group_and_subtype_mapping(self):
        for kind in ['house', 'apartment', 'condominium', 'apartment_condominium']:
            fields = {'property_type': kind, 'property_subtype': 'studio' if kind in
                      {'condominium', 'apartment_condominium'} else kind}
            row = self.adapter.prepare(fields)
            self.assertEqual(row.at[0, 'property_type'], 'house' if kind == 'house' else 'apartment_condominium')
            self.assertEqual(row.at[0, 'property_subtype'], fields['property_subtype'])
        for missing in [None, '', 'unknown', 'nan']:
            row = self.adapter.prepare({'property_type': 'apartment', 'property_subtype': missing})
            self.assertEqual(row.at[0, 'property_subtype'], 'apartment')

    def test_metadata_column_order_and_amenities(self):
        row = self.adapter.prepare({'property_type': 'house', 'city': ' Makati ',
                                    'amenities_normalized': ['gym', 'gym', 'unseen']})
        self.assertEqual(list(row.columns), self.adapter.metadata['input_columns'])
        self.assertEqual(row.at[0, 'city'], 'makati')
        for i, term in enumerate(self.adapter.vocabulary):
            self.assertEqual(row.at[0, f'amenity_{i:03d}'], int(term == 'gym'))
        pipe = self.adapter.prepare({'property_type': 'house', 'city': ' Makati ',
                                     'amenities_normalized': 'gym|gym|unseen'})
        assert_frame_equal(row, pipe)
        missing = self.adapter.prepare({'property_type': 'house'})
        empty = self.adapter.prepare({'property_type': 'house', 'amenities_normalized': ''})
        columns = [f'amenity_{i:03d}' for i in range(len(self.adapter.vocabulary))]
        self.assertTrue(missing[columns].isna().all().all())
        self.assertTrue((empty[columns] == 0).all().all())

    def test_invalid_inputs(self):
        for fields in [
            {'property_type': 'office'}, {'property_type': None},
            {'property_subtype': 'studio'}, {'city': []},
            {'bedrooms': 'oops'}, {'bedrooms': True}, {'bathrooms': -1},
            {'floor_area_sqm': float('inf')}, {'latitude': 91},
            {'longitude': -181}, {'amenities_normalized': [1]},
            {'amenities_normalized': {}}, {'property_type': 'apartment_condominium'},
        ]:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.adapter.prepare({'property_type': 'house', **fields})

    def test_metadata_validation(self):
        updates = [{}, {'configuration': {}}, {'amenity_vocabulary': ['gym', 'gym']},
                   {'model_types': ['office']}, {'prediction_inverse': 'identity'},
                   {'input_columns': list(reversed(self.adapter.columns))},
                   {'numeric_columns': list(reversed(self.adapter.metadata['numeric_columns']))}]
        for update in updates:
            metadata = {**copy.deepcopy(self.adapter.metadata), **update} if update else {}
            with self.subTest(update=update), self.assertRaises(ValueError):
                ModelBundle(metadata, self.adapter.preprocessor, self.adapter.model)

    def test_mismatched_model_width_rejected(self):
        with patch.object(type(self.adapter.model), 'n_features_in_', new_callable=lambda: property(lambda s: 1)):
            with self.assertRaisesRegex(ValueError, 'output width'):
                ModelBundle(self.adapter.metadata, self.adapter.preprocessor, self.adapter.model)

    def test_missing_export_fails_clearly(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'Cannot load portable model'):
                ModelBundle.load(Path(directory))

    def test_health_auth_and_invalid_inputs(self):
        self.assertEqual(self.client.get('/health').json(), {'status': 'ok'})
        fields = {'property_type': 'house'}
        with patch.dict(os.environ, {'ML_SHARED_SECRET': 'test-secret'}):
            for headers in [None, {'Authorization': 'Bearer wrong'}, {'Authorization': 'Basic wrong'}]:
                self.assertEqual(self.client.post('/predict', json=fields, headers=headers).status_code, 401)
            headers = {'Authorization': 'Bearer test-secret'}
            self.assertEqual(self.client.post('/predict', json={'property_type': 'office'}, headers=headers).status_code, 422)
            self.assertEqual(self.client.post('/predict', json=[], headers=headers).status_code, 422)
            for invalid in [float('nan'), float('inf'), 0, -1]:
                with patch.object(self.main.model_bundle, 'predict', return_value=invalid):
                    self.assertEqual(self.client.post('/predict', json=fields, headers=headers).status_code, 502)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.client.post('/predict', json=fields,
                headers={'Authorization': 'Bearer test-secret'}).status_code, 401)


if __name__ == '__main__':
    unittest.main()
