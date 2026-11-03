"""Validate vendored bytes and local HTML/CSS asset references without a browser."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'static'
VENDOR = STATIC / 'vendor' / 'pannellum-2.5.7'


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []
        self.ids = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'script' and 'src' in attrs:
            self.references.append(attrs['src'])
        if tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.references.append(attrs['href'])


class StaticTests(unittest.TestCase):
    def test_vendor_checksums(self):
        manifest = json.loads((VENDOR / 'provenance.json').read_text())
        self.assertEqual(manifest['version'], '2.5.7')
        self.assertEqual(set(manifest['files']), {'COPYING', 'VERSION', 'pannellum.js', 'pannellum.css'})
        for name, expected in manifest['files'].items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((VENDOR / name).read_bytes()).hexdigest(), expected)

    def test_html_dependencies_are_local_and_exist(self):
        document = References()
        document.feed((STATIC / 'index.html').read_text(encoding='utf-8-sig'))
        self.assertEqual(len(document.references), 4)
        for reference in document.references:
            self.assertTrue(reference.startswith('/') and not reference.startswith('//'))
            self.assertTrue((STATIC / reference.lstrip('/')).is_file())

    def test_css_has_no_external_assets(self):
        for path in STATIC.rglob('*.css'):
            css = path.read_text(encoding='utf-8-sig')
            self.assertNotIn('@import', css)
            for url in re.findall(r'url\((.*?)\)', css):
                self.assertTrue(url.strip("\"'").startswith('data:'), url)

    def test_app_dom_ids_exist_and_are_unique(self):
        document = References()
        document.feed((STATIC / 'index.html').read_text(encoding='utf-8-sig'))
        self.assertEqual(len(document.ids), len(set(document.ids)))
        script = (STATIC / 'app.js').read_text(encoding='utf-8-sig')
        for identifier in re.findall(r"el\('([^']+)'\)", script):
            self.assertIn(identifier, document.ids)

    def test_horizontal_page_dependencies_and_accessible_controls(self):
        document = References()
        document.feed((STATIC / 'horizontal.html').read_text(encoding='utf-8'))
        self.assertEqual(len(document.ids), len(set(document.ids)))
        for ref in document.references:
            self.assertTrue(ref.startswith('/') and not ref.startswith('//'))
            self.assertTrue((STATIC / ref.lstrip('/')).is_file())
        for identifier in re.findall(r"el\('([^']+)'\)", (STATIC / 'horizontal.js').read_text()):
            self.assertIn(identifier, document.ids)


if __name__ == '__main__':
    unittest.main()
