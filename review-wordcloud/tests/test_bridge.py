"""Focused protected NLP bridge tests; no model artifacts or production calls."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from wordcloud_api import router
app = FastAPI()
app.include_router(router)
P = '00000000-0000-4000-8000-000000000001'
R = '00000000-0000-4000-8000-000000000002'
S = '00000000-0000-4000-8000-000000000003'
async def request(target, path, body=None, token='test-nlp'):
    messages = []
    sent = False
    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {'type':'http.request','body':json.dumps(body, ensure_ascii=False).encode() if body is not None else b'', 'more_body':False}
        return {'type':'http.disconnect'}
    async def send(message): messages.append(message)
    headers = [(b'content-type', b'application/json')]
    if token is not None: headers.append((b'authorization', ('Bearer '+token).encode()))
    await target({'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1','method':'GET' if path=='/health' else 'POST','scheme':'http','path':path,'raw_path':path.encode(),'query_string':b'','root_path':'','headers':headers,'server':('localhost',1),'client':('localhost',2)},receive,send)
    status=next(m['status'] for m in messages if m['type']=='http.response.start')
    raw=b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
    return status,json.loads(raw)
class BridgeTests(unittest.TestCase):
    def call(self, body, token='test-nlp'):
        with patch.dict(os.environ, {'NLP_SHARED_SECRET':'test-nlp','ML_SHARED_SECRET':'different-ml'}):
            return asyncio.run(request(app,'/wordcloud',body,token))
    def corpus(self):
        return {'property_id':P,'corpus_version':'v','reviews':[{'id':R,'text':'?? Malinis ang room. Tahimik room.'},{'id':S,'text':'Malinis ang room, tahimik room.'}]}
    def test_protected_separate_secret_and_missing_configuration(self):
        for token in [None,'wrong','different-ml']:
            self.assertEqual(self.call(self.corpus(),token)[0],401)
        with patch.dict(os.environ, {'NLP_SHARED_SECRET':''}):
            self.assertEqual(asyncio.run(request(app,'/wordcloud',self.corpus()))[0],503)
    def test_same_ml_secret_is_rejected(self):
        with patch.dict(os.environ, {'NLP_SHARED_SECRET':'same','ML_SHARED_SECRET':'same'}):
            self.assertEqual(asyncio.run(request(app,'/wordcloud',self.corpus(),'same'))[0],503)
    def test_original_unicode_spans_distinct_counts_and_determinism(self):
        status,result=self.call(self.corpus());self.assertEqual(status,200)
        self.assertFalse(result['synthetic']);self.assertEqual(result['eligible_review_count'],2)
        term=next(t for t in result['terms'] if t['text']=='malinis')
        self.assertEqual(term['review_count'],2)
        originals={r['id']:r['text'] for r in self.corpus()['reviews']}
        for match in term['matches']:
            for span in match['spans']:
                self.assertEqual(originals[match['id']][span['start']:span['end']].casefold(),'malinis')
        self.assertEqual(result,self.call(self.corpus())[1])
    def test_rating_only_counts_and_empty(self):
        for text in [None,'','   ']:
            value=self.corpus();value['reviews']=[{'id':R,'text':text}]
            status,result=self.call(value);self.assertEqual(status,200);self.assertEqual(result['eligible_review_count'],1);self.assertEqual(result['status'],'insufficient_data');self.assertEqual(result['terms'],[])
        value=self.corpus();value['reviews']=[]
        self.assertEqual(self.call(value)[1]['status'],'empty')
    def test_invalid_duplicate_or_extra_sensitive_fields_rejected(self):
        for change in [lambda b:b.update(property_id='bad'),lambda b:b['reviews'].append(b['reviews'][0]),lambda b:b['reviews'][0].update(kind='user'),lambda b:b['reviews'][0].update(text='a'*2001)]:
            value=self.corpus();change(value);self.assertEqual(self.call(value)[0],422)
    def test_existing_ml_routes_mount_without_changing_auth(self):
        fake=MagicMock();fake.load.return_value={'preprocess':MagicMock(),'input_columns':[],'categorical_features':[],'model_types':[],'amenity_vocabulary':[]}
        spec=importlib.util.spec_from_file_location('bridge_ml_route_test',ROOT/'main.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {name:fake for name in ['joblib','numpy','pandas','xgboost','model_adapter']}):
            spec.loader.exec_module(module)
        paths=set(module.app.openapi()['paths'])
        self.assertTrue({'/health','/predict','/wordcloud'}<=paths)
        with patch.dict(os.environ, {'ML_SHARED_SECRET':'ml'}):
            self.assertEqual(asyncio.run(request(module.app,'/predict',{},'test-nlp'))[0],401)
            self.assertEqual(asyncio.run(request(module.app,'/health'))[1],{'status':'ok'})
