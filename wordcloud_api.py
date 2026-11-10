"""Server-to-server review NLP router. No database, fixture API, persistence or ML changes."""
from functools import lru_cache
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
import threading
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

router = APIRouter()
_slot = threading.BoundedSemaphore(1)

@lru_cache(maxsize=1)
def _processor_type():
    # Lazy load: missing NLP assets cannot prevent the existing ML app starting.
    path = Path(__file__).resolve().parent / 'review-wordcloud' / 'src' / 'processor.py'
    spec = importlib.util.spec_from_file_location('rentlease_review_processor', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.Processor

def _new_processor():
    class RequestProcessor(_processor_type()):
        """Reuse cloud/matching exactly; index and corpus exist for this request only."""
        def __init__(self):
            super().__init__()
            self._request_index = None
            self._request_cloud = None
        def _index(self, property_id, reviews):
            if self._request_index is None:
                self._request_index = super()._index(property_id, reviews)
            return self._request_index
        def cloud(self, property_id, reviews):
            if self._request_cloud is None:
                self._request_cloud = super().cloud(property_id, reviews)
            return self._request_cloud
    return RequestProcessor()

def _uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value.lower()
    except (ValueError, AttributeError):
        return False

def _process(value):
    if not isinstance(value, dict) or set(value) != {'property_id','corpus_version','reviews'}:
        raise ValueError()
    property_id, version, rows = value['property_id'], value['corpus_version'], value['reviews']
    if not _uuid(property_id) or not isinstance(version, str) or not version or not isinstance(rows, list) or len(rows) > 10020:
        raise ValueError()
    seen, eligible, chars = set(), [], 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'id','text'} or not _uuid(row['id']) or row['id'] in seen:
            raise ValueError()
        text = row['text']
        if text is not None and (not isinstance(text, str) or len(text) > 2000):
            raise ValueError()
        seen.add(row['id'])
        chars += len(text or '')
        if chars > 500000:
            raise ValueError()
        # These flags describe the trusted Edge-supplied corpus, NOT client authorization.
        eligible.append({'id':row['id'],'text':text,'property_id':property_id,'kind':'property',
                         'published':True,'visible':True,'moderation_status':'approved'})
    processor = _new_processor()
    cloud = processor.cloud(property_id, eligible)
    terms = []
    for term in cloud['terms']:
        matching = processor.matching(property_id, term['id'], eligible)
        terms.append({key:term[key] for key in ['id','text','review_count','color','font_size_rem']} |
                     {'matches':[{'id':r['id'],'spans':r['spans']} for r in matching['reviews']]})
    # T7A includes rating-only rows; NLP still excludes blank bodies from extraction.
    status = cloud['status'] if cloud['status'] != 'empty' or not rows else 'insufficient_data'
    return {'property_id':property_id,'corpus_version':version,'synthetic':False,
            'span_encoding':'unicode_code_points','eligible_review_count':len(rows),
            'usable_review_count':cloud['usable_review_count'],'thresholds':cloud['thresholds'],
            'status':status,'terms':terms}

@router.post('/wordcloud')
async def wordcloud(request: Request):
    expected = os.getenv('NLP_SHARED_SECRET')
    if not expected or expected == os.getenv('ML_SHARED_SECRET'):
        raise HTTPException(503, 'NLP unavailable')
    authorization = request.headers.get('authorization', '')
    scheme, _, supplied = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not supplied or not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, 'Unauthorized')
    if not _slot.acquire(blocking=False):
        raise HTTPException(429, 'NLP busy')
    try:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4 * 1024 * 1024:
                raise HTTPException(413, 'NLP input too large')
        try:
            value = json.loads(body)
            result = await run_in_threadpool(_process, value)
        except (ValueError, TypeError, KeyError, RecursionError, UnicodeError):
            raise HTTPException(422, 'Invalid NLP corpus') from None
        return JSONResponse(result, headers={'Cache-Control':'no-store'})
    finally:
        _slot.release()
