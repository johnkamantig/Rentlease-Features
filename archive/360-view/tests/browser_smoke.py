r"""Optional real desktop Chrome smoke tests. No physical Android claim.

From 360-view: .\.venv\Scripts\python.exe tests/browser_smoke.py -v
Install playwright==1.55.0 into .venv first; uses existing Chrome (no browser download).
"""
import io
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from playwright.sync_api import sync_playwright, expect
import server
from processor import make_demo_panorama


class QuietHandler(server.Handler):
    def log_message(self, *args):
        pass


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        cls.upload_patch = patch.object(server, 'UPLOADS', cls.directory / 'uploads')
        cls.upload_patch.start()
        cls.addClassCleanup(cls.upload_patch.stop)
        make_demo_panorama(server.UPLOADS / 'demo.jpg')
        cls.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.httpd.server_address[1])
        cls.addClassCleanup(cls.stop_server)
        cls.env_patch = patch.dict(os.environ, {'TEMP': str(cls.directory), 'TMP': str(cls.directory)})
        cls.env_patch.start()
        cls.addClassCleanup(cls.env_patch.stop)
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(channel='chrome', headless=True, args=['--enable-unsafe-swiftshader'])
        cls.addClassCleanup(cls.browser.close)
        print('Desktop Chrome:', cls.browser.version)

    @classmethod
    def stop_server(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 900})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.page.set_default_timeout(8000)
        self.external = []
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        def local_only(route):
            if route.request.url.startswith(self.base + '/'):
                route.continue_()
            else:
                self.external.append(route.request.url)
                route.abort()
        self.context.route('**/*', local_only)
        self.page.goto(self.base)

    def tearDown(self):
        self.assertEqual(self.external, [], 'Viewer must not request external resources')
        self.assertEqual(self.errors, [], 'Unexpected JavaScript errors')

    def grid(self):
        self.page.get_by_role('button', name='Try the 360').click()
        expect(self.page.locator('#message')).to_contain_text('Test grid loaded.')
        self.assertTrue(self.page.evaluate('viewer.isLoaded()'))
        expect(self.page.locator('#panorama canvas')).to_have_count(1)

    def test_real_grid_with_external_network_blocked(self):
        self.grid()
        expect(self.page.locator('#loading')).to_be_hidden()
        expect(self.page.locator('#viewerShell')).to_have_attribute('aria-busy', 'false')

    def test_loading_waits_for_real_image(self):
        pending = []
        self.page.route('**/uploads/demo.jpg', lambda route: pending.append(route))
        self.page.locator('#demoButton').click()
        expect(self.page.locator('#loading')).to_be_visible()
        expect(self.page.locator('#demoButton')).to_be_disabled()
        expect(self.page.locator('#imageInput')).to_be_disabled()
        expect(self.page.locator('#message')).not_to_contain_text('Test grid loaded.')
        self.page.wait_for_function("document.querySelector('#viewerName').textContent.startsWith('Loading:')")
        # Pump Playwright until the intercepted image request arrives.
        self.page.wait_for_timeout(100)
        self.assertEqual(len(pending), 1)
        pending[0].continue_()
        expect(self.page.locator('#message')).to_contain_text('Test grid loaded.')

    def test_upload_replaces_viewer_and_displays_stats(self):
        self.grid()
        self.page.evaluate('window.oldCanvas = document.querySelector("#panorama canvas")')
        data = io.BytesIO()
        with Image.new('RGB', (1024, 512), 'blue') as image:
            image.save(data, 'PNG')
        self.page.locator('#imageInput').set_input_files({'name': '<panorama>.png', 'mimeType': 'image/png', 'buffer': data.getvalue()})
        expect(self.page.locator('#message')).to_contain_text('Panorama loaded.')
        expect(self.page.locator('#viewerName')).to_have_text('<panorama>.png')
        expect(self.page.locator('#stats')).to_be_visible()
        expect(self.page.locator('#statsText')).to_contain_text('1024 x 512')
        self.assertFalse(self.page.evaluate('window.oldCanvas.isConnected'))
        expect(self.page.locator('#panorama canvas')).to_have_count(1)
        self.grid()
        expect(self.page.locator('#stats')).to_be_hidden()

    def test_image_http_error_and_recovery(self):
        self.page.route('**/uploads/demo.jpg', lambda route: route.fulfill(status=404, body='missing'))
        self.page.locator('#demoButton').click()
        expect(self.page.locator('#message')).to_contain_text('could not be displayed')
        expect(self.page.locator('#loading')).to_be_hidden()
        expect(self.page.locator('#demoButton')).to_be_enabled()
        expect(self.page.locator('#zoomIn')).to_be_disabled()
        self.page.unroute('**/uploads/demo.jpg')
        self.grid()

    def test_real_pannellum_webgl_error(self):
        self.page.evaluate('''() => {
          const original = HTMLCanvasElement.prototype.getContext;
          HTMLCanvasElement.prototype.getContext = function(type, ...args) {
            if (type.includes('webgl')) return null;
            return original.call(this, type, ...args);
          };
        }''')
        self.page.locator('#demoButton').click()
        expect(self.page.locator('#message')).to_contain_text('could not be displayed')
        expect(self.page.locator('#demoButton')).to_be_enabled()
        expect(self.page.locator('#loading')).to_be_hidden()

    def test_missing_library_is_actionable(self):
        self.page.route('**/pannellum.js', lambda route: route.abort())
        self.page.reload()
        self.page.locator('#demoButton').click()
        expect(self.page.locator('#message')).to_contain_text('local viewer library is missing')
        expect(self.page.locator('#demoButton')).to_be_enabled()
        expect(self.page.locator('#loading')).to_be_hidden()

    def test_http_error_and_invalid_json(self):
        self.page.route('**/api/demo', lambda route: route.fulfill(status=500, content_type='application/json', body='{"error":"Test server failure"}'))
        self.page.locator('#demoButton').click()
        expect(self.page.locator('#message')).to_have_text('Test server failure')
        self.page.unroute('**/api/demo')
        self.page.route('**/api/demo', lambda route: route.fulfill(status=200, body='not JSON'))
        self.page.locator('#demoButton').click()
        expect(self.page.locator('#message')).to_contain_text('unreadable response')
        expect(self.page.locator('#demoButton')).to_be_enabled()

    def test_network_failure(self):
        self.page.route('**/api/demo', lambda route: route.abort())
        self.page.locator('#demoButton').click()
        expect(self.page.locator('#message')).to_contain_text('Cannot reach the local server')
        expect(self.page.locator('#loading')).to_be_hidden()

    def test_viewer_timeout(self):
        self.page.clock.install()
        pending = []
        self.page.route('**/uploads/demo.jpg', lambda route: pending.append(route))
        self.page.locator('#demoButton').click()
        self.page.wait_for_function("document.querySelector('#viewerName').textContent.startsWith('Loading:')")
        self.page.clock.fast_forward(30001)
        expect(self.page.locator('#message')).to_contain_text('Viewer loading timed out')
        expect(self.page.locator('#demoButton')).to_be_enabled()
        self.assertEqual(len(pending), 1)
        pending[0].abort()
        self.page.unroute('**/uploads/demo.jpg')

    def test_fullscreen_fallback_and_escape(self):
        self.grid()
        self.page.evaluate('document.querySelector("#viewerShell").requestFullscreen = undefined')
        self.page.locator('#fullscreenButton').click()
        expect(self.page.locator('#fullscreenButton')).to_have_attribute('aria-pressed', 'true')
        self.assertTrue(self.page.locator('#viewerShell').evaluate('node => node.classList.contains("expanded")'))
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#fullscreenButton')).to_have_attribute('aria-pressed', 'false')
        expect(self.page.locator('#fullscreenButton')).to_be_focused()
        self.assertFalse(self.page.locator('body').evaluate('node => node.classList.contains("viewer-expanded")'))
        self.page.evaluate('() => { document.querySelector("#viewerShell").requestFullscreen = () => Promise.reject(new Error("denied")); }')
        self.page.locator('#fullscreenButton').click()
        expect(self.page.locator('#fullscreenButton')).to_have_text('Exit fullscreen')
        self.page.locator('#fullscreenButton').click()
        expect(self.page.locator('#fullscreenButton')).to_have_text('Fullscreen')

    def test_native_fullscreen_and_zoom_keyboard(self):
        self.grid()
        initial = self.page.evaluate('viewer.getHfov()')
        self.page.locator('#zoomIn').click()
        self.page.wait_for_function('viewer.getHfov() < ' + str(initial))
        self.page.locator('#fullscreenButton').click()
        self.page.wait_for_function('document.fullscreenElement === document.querySelector("#viewerShell")')
        self.page.locator('#fullscreenButton').click()
        self.page.wait_for_function('document.fullscreenElement === null')
        self.page.locator('#panorama').focus()
        self.page.keyboard.down('ArrowLeft')
        try:
            self.page.wait_for_function('Math.abs(viewer.getYaw()) > 0.1')
        finally:
            self.page.keyboard.up('ArrowLeft')

    def test_mobile_width_layout(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.grid()
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        expect(self.page.locator('#fullscreenButton')).to_be_visible()
        expect(self.page.locator('#imageInput')).to_be_visible()

    def flat_image(self, size=(3000, 750), name='wide.png'):
        data = io.BytesIO()
        with Image.new('RGB', size, 'steelblue') as image:
            image.save(data, 'PNG')
        self.page.locator('#imageInput').set_input_files({'name': name, 'mimeType': 'image/png', 'buffer': data.getvalue()})
        expect(self.page.locator('#message')).to_contain_text('Image loaded.')

    def test_flat_wide_image_preserves_proportions_and_uses_only_local_assets(self):
        self.page.goto(self.base + '/horizontal.html')
        self.flat_image()
        expect(self.page.locator('#stats')).to_contain_text('3000 × 750')
        ratio = self.page.locator('#photo').evaluate('im => im.getBoundingClientRect().width / im.getBoundingClientRect().height')
        self.assertAlmostEqual(ratio, 4, places=2)
        expect(self.page.locator('#loading')).to_be_hidden()
        self.assertFalse(self.page.evaluate('Boolean(window.pannellum)'))

    def test_flat_keyboard_zoom_and_drag(self):
        self.page.goto(self.base + '/horizontal.html')
        self.flat_image()
        self.page.locator('#zoomIn').click()
        expect(self.page.locator('#zoomLevel')).to_have_text('150% of fit')
        self.page.locator('#viewport').focus()
        before = self.page.locator('#viewport').evaluate('v => v.scrollLeft')
        self.page.keyboard.press('ArrowRight')
        self.assertGreater(self.page.locator('#viewport').evaluate('v => v.scrollLeft'), before)
        box = self.page.locator('#viewport').bounding_box()
        before = self.page.locator('#viewport').evaluate('v => v.scrollLeft')
        self.page.mouse.move(box['x'] + 500, box['y'] + 100)
        self.page.mouse.down()
        self.page.mouse.move(box['x'] + 400, box['y'] + 100, steps=5)
        self.page.mouse.up()
        self.assertGreater(self.page.locator('#viewport').evaluate('v => v.scrollLeft'), before)
        self.page.keyboard.press('0')
        expect(self.page.locator('#zoomLevel')).to_have_text('100% of fit')

    def test_flat_replacement_and_failed_upload_keep_previous_image(self):
        self.page.goto(self.base + '/horizontal.html')
        self.flat_image()
        first = self.page.locator('#photo').get_attribute('src')
        self.flat_image((1500, 1000), '<replacement>.png')
        expect(self.page.locator('#viewerName')).to_have_text('<replacement>.png')
        second = self.page.locator('#photo').get_attribute('src')
        self.assertNotEqual(first, second)
        self.page.locator('#imageInput').set_input_files({'name': 'bad.png', 'mimeType': 'image/png', 'buffer': b'broken'})
        expect(self.page.locator('#message')).to_contain_text('Cannot decode')
        self.assertEqual(self.page.locator('#photo').get_attribute('src'), second)
        expect(self.page.locator('#zoomIn')).to_be_enabled()

    def test_flat_download_error_and_recovery(self):
        self.page.goto(self.base + '/horizontal.html')
        self.page.route('**/uploads/demo.jpg', lambda route: route.fulfill(status=404, body='missing'))
        self.page.locator('#demoButton').click()
        expect(self.page.locator('#message')).to_contain_text('could not be loaded')
        expect(self.page.locator('#loading')).to_be_hidden()
        self.page.unroute('**/uploads/demo.jpg')
        self.page.locator('#demoButton').click()
        expect(self.page.locator('#message')).to_contain_text('Image loaded.')

    def test_flat_loading_timeout_and_recovery(self):
        self.page.goto(self.base + '/horizontal.html')
        self.page.clock.install()
        pending = []
        self.page.route('**/api/demo', lambda route: pending.append(route))
        self.page.locator('#demoButton').click()
        expect(self.page.locator('#loading')).to_be_visible()
        expect(self.page.locator('#imageInput')).to_be_disabled()
        self.page.clock.fast_forward(60001)
        expect(self.page.locator('#message')).to_contain_text('timed out')
        expect(self.page.locator('#demoButton')).to_be_enabled()
        for route in pending:
            route.abort()

    def test_flat_fullscreen_fallback_and_escape(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.goto(self.base + '/horizontal.html')
        self.flat_image()
        self.page.evaluate('document.querySelector("#viewerShell").requestFullscreen = undefined')
        self.page.locator('#fullscreenButton').click()
        expect(self.page.locator('#fullscreenButton')).to_have_attribute('aria-pressed', 'true')
        self.assertTrue(self.page.locator('#viewport').evaluate('v => v.getBoundingClientRect().bottom <= innerHeight'))
        self.assertTrue(self.page.locator('#viewerName').evaluate('v => v.getBoundingClientRect().bottom <= innerHeight'))
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#fullscreenButton')).to_have_attribute('aria-pressed', 'false')
        expect(self.page.locator('#fullscreenButton')).to_be_focused()

    def test_flat_mobile_layout_and_two_finger_pinch(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.goto(self.base + '/horizontal.html')
        self.flat_image()
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        box = self.page.locator('#viewport').bounding_box()
        cdp = self.context.new_cdp_session(self.page)
        def touches(a, b):
            return [{'x': box['x'] + a, 'y': box['y'] + 100, 'id': 1},
                    {'x': box['x'] + b, 'y': box['y'] + 100, 'id': 2}]
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': touches(100, 200)})
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': touches(50, 250)})
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        self.page.wait_for_function('zoom > 1.5')
        self.page.locator('#fit').click()
        expect(self.page.locator('#zoomLevel')).to_have_text('100% of fit')

    def test_spherical_page_redirects_wide_images_to_flat_viewer(self):
        data = io.BytesIO()
        with Image.new('RGB', (3000, 750), 'blue') as image:
            image.save(data, 'PNG')
        self.page.locator('#imageInput').set_input_files({'name': 'wide.png', 'mimeType': 'image/png', 'buffer': data.getvalue()})
        expect(self.page.locator('#message')).to_contain_text('horizontal panorama viewer')
        expect(self.page.locator('#panorama canvas')).to_have_count(0)


if __name__ == '__main__':
    unittest.main()
