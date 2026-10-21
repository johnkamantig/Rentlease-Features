
import os
import secrets
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from xgboost import XGBRegressor

app = FastAPI(title="RentLease ML API")
bearer_scheme = HTTPBearer(auto_error=False)
# Load trained model components
MODEL_DIR = Path(__file__).resolve().parent / "models"

bundle = joblib.load(
    MODEL_DIR / "rentlease_preprocessor.joblib"
)

preprocessor = bundle["preprocess"]
feature_columns = bundle["input_columns"]
categorical = bundle["categorical_features"]
supported_types = bundle["model_types"]
amenity_vocabulary = bundle["amenity_vocabulary"]

model = XGBRegressor()
model.load_model(str(MODEL_DIR / "rentlease_model.ubj"))

print("RentLease XGBoost model loaded successfully!")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
def predict(
    features: dict,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    expected = os.getenv("ML_SHARED_SECRET")

    if (
        not expected
        or credentials is None
        or not secrets.compare_digest(
            credentials.credentials,
            expected
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )

    # Only allow property types included in training
    property_type = str(
        features.get("property_type", "")
    ).strip().lower()

    if property_type not in supported_types:
        raise HTTPException(
            status_code=422,
            detail="Unsupported property type",
        )

    # Prepare the original 79 model features
    row = pd.DataFrame([{
        col: features.get(col, np.nan)
        for col in feature_columns
    }])

    # Normalize categorical values
    for col in categorical:
        row[col] = (
            row[col]
            .astype("string")
            .str.strip()
            .str.lower()
            .fillna("unknown")
            .astype(str)
        )

    # Process amenities using the training vocabulary
    if "amenities_normalized" in features:
        provided = features["amenities_normalized"]

        if isinstance(provided, str):
            provided = provided.split("|")

        if provided is not None:
            if not isinstance(provided, list) or not all(
                isinstance(item, str) for item in provided
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Invalid amenities format",
                )

            selected = {
                item.strip().lower() for item in provided
            }

            for i, term in enumerate(amenity_vocabulary):
                row[f"amenity_{i:03d}"] = int(
                    term in selected
                )

    # Convert numeric features
    numeric = [
        col for col in feature_columns
        if col not in categorical
    ]

    row[numeric] = row[numeric].apply(
        pd.to_numeric, errors="coerce"
    )

    # Apply trained preprocessing
    processed = preprocessor.transform(row)

    # Predict log-transformed monthly rental price
    raw_prediction = float(
        model.predict(processed)[0]
    )

    # Convert back to PHP
    prediction = float(np.expm1(raw_prediction))

    if not np.isfinite(prediction) or prediction <= 0:
        raise HTTPException(
            status_code=502,
            detail="Invalid model prediction",
        )

    return {
        "estimated_rent_monthly": round(prediction, 2),
        "range_min": round(prediction * 0.70, 2),
        "range_max": round(prediction * 1.30, 2),
        "currency": "PHP",
        "model_version": "development-v1",
    }
