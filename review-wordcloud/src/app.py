"""Local-only synthetic API. No production authorization contract."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .processor import Processor

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "fixtures/reviews.json").read_text(encoding="utf-8"))
processor = Processor()
app = FastAPI(title="RentLease synthetic word cloud", version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


def check_property(property_id):
    if not any(p["id"] == property_id for p in DATA["properties"]):
        raise HTTPException(404, "Unknown synthetic property")


@app.get("/", include_in_schema=False)
def viewer():
    return FileResponse(ROOT / "web/index.html")


@app.get("/health")
def health():
    return {"status": "ok", "synthetic": True}


@app.get("/properties")
def properties():
    return DATA["properties"]


@app.get("/properties/{property_id}/wordcloud")
def wordcloud(property_id: str):
    check_property(property_id)
    return processor.cloud(property_id, DATA["reviews"])


@app.get("/properties/{property_id}/wordcloud/terms/{term_id}/reviews")
def matching(property_id: str, term_id: str):
    check_property(property_id)
    try:
        return processor.matching(property_id, term_id, DATA["reviews"])
    except KeyError:
        raise HTTPException(404, "Term not available for this property") from None
