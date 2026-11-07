import os
import secrets
from pathlib import Path

import numpy as np
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from model_adapter import ModelBundle

app = FastAPI(title="RentLease ML API")
bearer_scheme = HTTPBearer(auto_error=False)
MODEL_DIR = Path(__file__).resolve().parent / "models"
model_bundle = ModelBundle.load(MODEL_DIR)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
def predict(
    features: dict,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    expected = os.getenv("ML_SHARED_SECRET")
    if (not expected or credentials is None
            or not secrets.compare_digest(credentials.credentials, expected)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        row = model_bundle.prepare(features)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    prediction = model_bundle.predict(row)
    if not np.isfinite(prediction) or prediction <= 0:
        raise HTTPException(status_code=502, detail="Invalid model prediction")
    return {
        "estimated_rent_monthly": round(prediction, 2),
        "range_min": round(prediction * 0.70, 2),
        "range_max": round(prediction * 1.30, 2),
        "currency": "PHP",
        "model_version": "development-v1",
    }
