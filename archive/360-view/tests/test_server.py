"""Exercise a real loopback HTTP server with isolated files and raw HTTP failures."""
import http.client
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from processor import make_demo_panorama
from test_processor import image_bytes


class QuietHandler(server.Handler):
    def log_message(self, *args):
        pass


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        cls.uploads = Path(cls.temp.name) / 'uploads'
        cls.uploads.mkdir()
        cls.patch = patch.object(server, 'UPLOADS', cls.uploads)
        cls.patch.start()
        cls.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()
        cls.patch.stop()
        cls.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def raw(self, request):
        with socket.create_connection(('127.0.0.1', self.port), timeout=5) as sock:
            sock.sendall(request)
            sock.shutdown(socket.SHUT_WR)
            chunks = []
            while chunk := sock.recv(65536):
                chunks.append(chunk)
        response = b''.join(chunks)
        headers, body = response.split(b'\r\n\r\n', 1)
        return int(headers.split()[1]), json.loads(body)

    def test_static_files_and_local_vendor(self):
        paths = {'/': 'text/html', '/index.html': 'text/html', '/app.js': 'text/javascript', '/style.css': 'text/css', '/vendor/pannellum-2.5.7/pannellum.js': 'text/javascript', '/vendor/pannellum-2.5.7/pannellum.css': 'text/css'}
        for path, content_type in paths.items():
            with self.subTest(path=path):
                status, headers, data = self.request('GET', path)
                self.assertEqual(status, 200)
                self.assertEqual(headers['Content-Type'], content_type)
                self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
                self.assertEqual(int(headers['Content-Length']), len(data))
                self.assertTrue(data)

    def test_vendor_license_and_version(self):
        for name, expected in [('COPYING', b'Permission is hereby granted'), ('VERSION', b'2.5.7')]:
            status, _, data = self.request('GET', '/vendor/pannellum-2.5.7/' + name)
            self.assertEqual(status, 200)
            self.assertIn(expected, data)

    def test_upload_success_and_download_for_all_formats(self):
        for format in ('JPEG', 'PNG', 'WEBP'):
            with self.subTest(format=format):
                status, headers, data = self.request('POST', '/api/upload', image_bytes(format=format), {'Content-Type': 'application/octet-stream'})
                self.assertEqual(status, 201)
                self.assertEqual(headers['Cache-Control'], 'no-store')
                payload = json.loads(data)
                self.assertEqual((payload['width'], payload['height']), (1024, 512))
                status, headers, jpeg = self.request('GET', payload['url'])
                self.assertEqual(status, 200)
                self.assertEqual(headers['Content-Type'], 'image/jpeg')
                self.assertEqual(len(jpeg), payload['output_bytes'])
                self.assertEqual(jpeg[:2], b'\xff\xd8')

    def test_demo_success_and_file(self):
        make_demo_panorama(self.uploads / 'demo.jpg')
        status, _, data = self.request('GET', '/api/demo')
        self.assertEqual(status, 200)
        status, _, image = self.request('GET', json.loads(data)['url'])
        self.assertEqual(status, 200)
        self.assertTrue(image.startswith(b'\xff\xd8'))

    def test_missing_demo(self):
        (self.uploads / 'demo.jpg').unlink(missing_ok=True)
        status, _, data = self.request('GET', '/api/demo')
        self.assertEqual(status, 404)
        self.assertIn('missing', json.loads(data)['error'])

    def test_bad_image_is_clean_json(self):
        before = set(self.uploads.iterdir())
        status, _, data = self.request('POST', '/api/upload', b'not an image')
        self.assertEqual(status, 400)
        self.assertIn('Cannot decode', json.loads(data)['error'])
        self.assertEqual(before, set(self.uploads.iterdir()))

    def test_invalid_dimensions(self):
        status, _, data = self.request('POST', '/api/upload', image_bytes((1000, 200)))
        self.assertEqual(status, 400)
        self.assertIn('too small', json.loads(data)['error'])

    def test_wide_upload_and_horizontal_assets(self):
        status, _, data = self.request('POST', '/api/upload', image_bytes((3000, 750)))
        self.assertEqual(status, 201)
        result = json.loads(data)
        self.assertEqual((result['width'], result['height']), (3000, 750))
        for path in ('/horizontal.html', '/horizontal.js', '/horizontal.css'):
            self.assertEqual(self.request('GET', path)[0], 200)

    def test_empty_body(self):
        self.assertEqual(self.request('POST', '/api/upload', b'')[0], 413)

    def test_oversized_length_rejected_before_read(self):
        status, payload = self.raw(b'POST /api/upload HTTP/1.0\r\nContent-Length: 26214401\r\n\r\n')
        self.assertEqual(status, 413)
        self.assertIn('25 MiB', payload['error'])

    def test_missing_content_length(self):
        self.assertEqual(self.raw(b'POST /api/upload HTTP/1.0\r\n\r\n')[0], 411)

    def test_invalid_content_lengths(self):
        for length in (b'-1', b'NaN', b'1, 2', b'+1', b'9' * 100):
            with self.subTest(length=length):
                self.assertEqual(self.raw(b'POST /api/upload HTTP/1.0\r\nContent-Length: ' + length + b'\r\n\r\n')[0], 411)

    def test_duplicate_content_length(self):
        self.assertEqual(self.raw(b'POST /api/upload HTTP/1.0\r\nContent-Length: 1\r\nContent-Length: 2\r\n\r\nx')[0], 411)

    def test_chunked_upload_rejected(self):
        self.assertEqual(self.raw(b'POST /api/upload HTTP/1.0\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n')[0], 400)

    def test_incomplete_body(self):
        status, payload = self.raw(b'POST /api/upload HTTP/1.0\r\nContent-Length: 100\r\n\r\nx')
        self.assertEqual(status, 400)
        self.assertEqual(payload['error'], 'Incomplete upload.')

    def test_body_timeout(self):
        with patch.object(server, 'READ_TIMEOUT', 0.1):
            with socket.create_connection(('127.0.0.1', self.port), timeout=5) as sock:
                sock.sendall(b'POST /api/upload HTTP/1.0\r\nContent-Length: 100\r\n\r\nx')
                response = http.client.HTTPResponse(sock)
                response.begin()
                self.assertEqual(response.status, 408)
                self.assertIn('timed out', json.loads(response.read())['error'])

    def test_busy_upload_rejected(self):
        with server.UPLOAD_SLOT:
            status, _, data = self.request('POST', '/api/upload', b'x')
        self.assertEqual(status, 503)
        self.assertIn('Another image', json.loads(data)['error'])

    def test_storage_failure_is_clean_and_releases_slot(self):
        with patch.object(server, 'process_panorama', side_effect=OSError('C:/private/path secret detail')):
            status, _, data = self.request('POST', '/api/upload', b'x')
        self.assertEqual(status, 500)
        self.assertNotIn(b'private', data)
        self.assertIn('Cannot save', json.loads(data)['error'])
        self.assertTrue(server.UPLOAD_SLOT.acquire(blocking=False))
        server.UPLOAD_SLOT.release()

    def test_missing_file(self):
        self.assertEqual(self.request('GET', '/uploads/' + 'a' * 32 + '.jpg')[0], 404)

    def test_unknown_post_path(self):
        self.assertEqual(self.request('POST', '/api/other', b'x')[0], 404)

    def test_path_restrictions(self):
        for path in ('/processor.py', '/server.py', '/README.md', '/.venv/pyvenv.cfg', '/uploads/', '/uploads/../processor.py', '/uploads/%2e%2e%2fprocessor.py', '/uploads/%252e%252e%252fprocessor.py', '/uploads/..\\processor.py', '/uploads/demo.jpg/extra', '/uploads/demo.jpg%00', '/uploads/demo.jpg:stream', '/uploads/DEMO.jpg', '/static/app.js', '/vendor/pannellum-2.5.7/../app.js', '/vendor/pannellum-2.5.7/provenance.json', '/vendor/pannellum-2.5.7/pannellum.js/extra', '/api/upload'):
            with self.subTest(path=path):
                self.assertEqual(self.request('GET', path)[0], 404)

    def test_query_string_does_not_change_allowlist(self):
        self.assertEqual(self.request('GET', '/app.js?cache=1')[0], 200)
        self.assertEqual(self.request('GET', '/server.py?file=app.js')[0], 404)

    def test_resolved_path_escape_is_rejected(self):
        outside = Path(self.temp.name) / 'outside.jpg'
        outside.write_bytes(b'private')
        self.assertFalse(server.Handler.allowed_file(outside, self.uploads))
        # Mock resolution to cover Windows junction / symlink escape without admin privileges.
        original = Path.resolve
        def resolve(path, *args, **kwargs):
            if path == self.uploads / 'demo.jpg':
                return outside
            return original(path, *args, **kwargs)
        with patch.object(Path, 'resolve', resolve):
            self.assertEqual(self.request('GET', '/uploads/demo.jpg')[0], 404)

    def test_file_read_failure_is_clean(self):
        with patch.object(Path, 'open', side_effect=PermissionError('private path')):
            status, _, data = self.request('GET', '/app.js')
        self.assertEqual(status, 500)
        self.assertNotIn(b'private', data)


if __name__ == '__main__':
    unittest.main()
