"""Exercise the real ASGI app with stdlib-only HTTP transport."""
import asyncio
import json
import unittest

from src.app import app


async def request(path):
    messages = []
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message):
        messages.append(message)
    await app({"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"}, "http_version": "1.1",
               "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
               "query_string": b"", "root_path": "", "headers": [],
               "server": ("127.0.0.1", 8001), "client": ("127.0.0.1", 1234)}, receive, send)
    status = next(m["status"] for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return status, body


class ApiTests(unittest.TestCase):
    def get(self, path):
        status, body = asyncio.run(request(path))
        return status, json.loads(body)

    def test_health_cloud_and_exact_linked_reviews(self):
        self.assertEqual(self.get('/health')[0], 200)
        status, cloud = self.get('/properties/demo/wordcloud')
        self.assertEqual(status, 200)
        self.assertEqual(cloud['eligible_review_count'], 12)
        self.assertEqual(cloud['status'], 'ready')
        parking = next(t for t in cloud['terms'] if t['text'] == 'parking')
        status, matches = self.get('/properties/demo/wordcloud/terms/' + parking['id'] + '/reviews')
        self.assertEqual(status, 200)
        self.assertEqual(len(matches['reviews']), parking['review_count'])
        for review in matches['reviews']:
            for span in review['spans']:
                self.assertEqual(review['text'][span['start']:span['end']].casefold(), 'parking')
        self.assertEqual(self.get('/properties/empty/wordcloud/terms/' + parking['id'] + '/reviews')[0], 404)

    def test_states_unknown_and_static_viewer(self):
        self.assertEqual(self.get('/properties/empty/wordcloud')[1]['status'], 'empty')
        self.assertEqual(self.get('/properties/sparse/wordcloud')[1]['status'], 'insufficient_data')
        self.assertEqual(self.get('/properties/unknown/wordcloud')[0], 404)
        self.assertEqual(self.get('/properties/demo/wordcloud/terms/invalid/reviews')[0], 404)
        for path in ['/', '/static/app.js', '/static/styles.css', '/static/highlight.js']:
            self.assertEqual(asyncio.run(request(path))[0], 200)
