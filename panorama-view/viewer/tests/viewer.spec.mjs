import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

const jpeg = await readFile(new URL('../fixtures/synthetic.jpg', import.meta.url));
const metadata = JSON.parse(await readFile(new URL('../fixtures/synthetic.json', import.meta.url)));
const status = page => page.locator('#status');
async function load(page, which) {
  await page.goto('/');
  await page.locator(`#${which}`).click();
  await expect(status(page)).toHaveAttribute('data-state', 'ready');
}
async function state(page) {
  return page.evaluate(async () => {
    const v = (await import('/app.mjs')).currentViewer();
    return { yaw: v.getYaw(), pitch: v.getPitch(), hfov: v.getHfov(), bounds: v.getHfovBounds(),
      config: v.getConfig(), width: v.getRenderer().getCanvas().width, height: v.getRenderer().getCanvas().height };
  });
}
async function look(page, pitch, yaw, hfov) {
  await page.evaluate(async ({ pitch, yaw, hfov }) => {
    const v = (await import('/app.mjs')).currentViewer();
    v.stopMovement(); v.lookAt(pitch, yaw, hfov, false);
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  }, { pitch, yaw, hfov });
}
async function renderMetrics(page, comparisonYaw) {
  return page.evaluate(async comparisonYaw => {
    const v = (await import('/app.mjs')).currentViewer();
    const renderer = v.getRenderer(), canvas = renderer.getCanvas();
    const scratch = document.createElement('canvas'); scratch.width = canvas.width; scratch.height = canvas.height;
    const ctx = scratch.getContext('2d', { willReadFrequently: true });
    const capture = yaw => {
      renderer.render(v.getPitch() * Math.PI / 180, yaw * Math.PI / 180, v.getHfov() * Math.PI / 180);
      ctx.drawImage(canvas, 0, 0);
      return ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    };
    const first = capture(v.getYaw());
    let black = 0, total = 0, sum = 0;
    for (let i = 0; i < first.length; i += 4) {
      if (first[i] < 5 && first[i + 1] < 5 && first[i + 2] < 5) black++;
      sum += first[i] + first[i+1] + first[i+2]; total++;
    }
    let difference = 0;
    if (comparisonYaw !== undefined) {
      const other = capture(comparisonYaw);
      for (let i = 0; i < first.length; i += 4) {
        difference += Math.abs(first[i]-other[i]) + Math.abs(first[i+1]-other[i+1]) + Math.abs(first[i+2]-other[i+2]);
      }
      difference /= total * 3;
    }
    const edges = [];
    for (let x = 1; x < canvas.width; x++) {
      let edge = 0;
      for (let y = 0; y < canvas.height; y++) {
        const i = (y * canvas.width + x) * 4;
        edge += Math.abs(first[i]-first[i-4]) + Math.abs(first[i+1]-first[i-3]) + Math.abs(first[i+2]-first[i-2]);
      }
      edges.push(edge / (canvas.height * 3));
    }
    const center = edges[Math.floor(canvas.width / 2) - 1];
    const p95 = [...edges].sort((a,b) => a-b)[Math.floor(edges.length * .95)];
    return { blackFraction: black / total, average: sum / (3 * total), difference, centerJump: center, ordinaryEdgeP95: p95 };
  }, comparisonYaw);
}
async function upload(page, data, image = jpeg) {
  await page.locator('#image-file').setInputFiles({ name: 'panorama.jpg', mimeType: 'image/jpeg', buffer: image });
  await page.locator('#metadata-file').setInputFiles({ name: 'panorama.json', mimeType: 'application/json',
    buffer: Buffer.from(typeof data === 'string' ? data : JSON.stringify(data)) });
  await page.getByRole('button', { name: 'Open panorama', exact: true }).click();
}

// Single worker and ordered tests: establish the independent reference before
// asserting the behavior of the processed strip.
test('01 known-good reference sphere renders and wraps', async ({ page }, testInfo) => {
  await load(page, 'reference');
  const s = await state(page);
  expect([s.config.haov, s.config.vaov, s.config.vOffset]).toEqual([360, 180, 0]);
  await look(page, 0, 179.9, 90);
  const seam = await renderMetrics(page, -180.1);
  expect(seam.average).toBeGreaterThan(30);
  expect(seam.blackFraction).toBe(0);
  expect(seam.difference).toBeLessThan(.05);
  await page.screenshot({ path: testInfo.outputPath('reference.png') });
});

test('02 Phase 2 metadata, full turns by mouse, and wrap continuity', async ({ page }, testInfo) => {
  await load(page, 'synthetic');
  let s = await state(page);
  expect([s.config.haov, s.config.vaov, s.config.vOffset]).toEqual([360, metadata.vertical_coverage_deg, metadata.vertical_offset_deg]);
  const box = await page.locator('#panorama').boundingBox();
  for (const direction of [1, -1]) {
    let total = 0;
    for (let n = 0; n < 10; n++) {
      const start = await state(page);
      await page.mouse.move(box.x + box.width * (direction === 1 ? .8 : .2), box.y + box.height / 2);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width * (direction === 1 ? .2 : .8), box.y + box.height / 2, { steps: 12 });
      await page.mouse.up();
      await page.evaluate(async () => (await import('/app.mjs')).currentViewer().stopMovement());
      const end = await state(page);
      const delta = ((end.yaw - start.yaw + 540) % 360) - 180;
      expect(Math.abs(delta)).toBeGreaterThan(15);
      total += delta;
    }
    expect(Math.abs(total)).toBeGreaterThan(360);
  }
  await look(page, metadata.vertical_offset_deg, 179.9, 70);
  expect((await renderMetrics(page, -180.1)).difference).toBeLessThan(.05);
  expect((await renderMetrics(page, -179.9)).difference).toBeLessThan(8);
  // Equivalent yaw alone cannot detect a clamped texture-edge line. At an
  // exact boundary, require interpolation comparable to ordinary image edges.
  await look(page, 0, 180, 70);
  const boundary = await renderMetrics(page);
  expect(boundary.centerJump).toBeLessThan(boundary.ordinaryEdgeP95 * 1.7);
  await testInfo.attach('boundary-metrics', { body: JSON.stringify(boundary), contentType: 'application/json' });
  await page.screenshot({ path: testInfo.outputPath('synthetic-wrap.png') });
});

test('03 pitch bounds, zoom, all yaw sectors and resizing show no missing areas', async ({ page }, testInfo) => {
  await load(page, 'synthetic');
  const initial = (await state(page)).hfov;
  await page.locator('.pnlm-zoom-in').click();
  await expect.poll(async () => (await state(page)).hfov).toBeLessThan(initial - 2);
  await page.locator('#panorama').hover();
  await page.mouse.wheel(0, 300);
  await expect.poll(async () => (await state(page)).hfov).toBeGreaterThan(initial - 2);
  for (const viewport of [{ width: 1100, height: 760 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    for (const pitch of [-90, 0, 90]) {
      for (const yaw of [-180, -90, 0, 90, 180]) {
        await look(page, pitch, yaw, 150);
        const s = await state(page);
        const vfov = 2 * Math.atan(Math.tan(s.hfov * Math.PI / 360) * s.height / s.width) * 180 / Math.PI;
        expect(s.pitch - vfov / 2).toBeGreaterThanOrEqual(metadata.vertical_offset_deg - metadata.vertical_coverage_deg / 2 - .01);
        expect(s.pitch + vfov / 2).toBeLessThanOrEqual(metadata.vertical_offset_deg + metadata.vertical_coverage_deg / 2 + .01);
        const pixels = await renderMetrics(page);
        expect(pixels.average).toBeGreaterThan(30);
        expect(pixels.blackFraction).toBe(0);
      }
    }
  }
  await page.screenshot({ path: testInfo.outputPath('portrait.png') });
});

test('04 browser-emulated touch dragging and pinch zoom', async ({ browser }, testInfo) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  await load(page, 'synthetic');
  const client = await context.newCDPSession(page);
  const box = await page.locator('#panorama').boundingBox();
  const y = box.y + box.height / 2, x = box.width / 2;
  const touch = (type, points) => client.send('Input.dispatchTouchEvent', { type, touchPoints: points.map(([px, py], id) => ({ x: px, y: py, id })) });
  const before = await state(page);
  await touch('touchStart', [[x+90, y]]);
  for (let i=1; i<=10; i++) await touch('touchMove', [[x+90-i*18, y]]);
  await touch('touchEnd', []);
  expect(Math.abs((await state(page)).yaw - before.yaw)).toBeGreaterThan(10);
  await look(page, metadata.vertical_offset_deg, 0, before.hfov);
  await touch('touchStart', [[x-30, y], [x+30, y]]);
  for (let i=1; i<=8; i++) await touch('touchMove', [[x-30-i*8, y], [x+30+i*8, y]]);
  await touch('touchEnd', []);
  expect((await state(page)).hfov).toBeLessThan(before.hfov - 3);
  expect((await renderMetrics(page)).blackFraction).toBe(0);
  await page.screenshot({ path: testInfo.outputPath('emulated-pinch.png') });
  await context.close();
});

test('05 invalid metadata, wrong images and corrupt JPEG fail; valid retry works', async ({ page }) => {
  await page.goto('/');
  for (const data of ['{broken', { ...metadata, vertical_offset_deg: undefined }, { ...metadata, closure_verified: false }]) {
    await upload(page, data);
    await expect(status(page)).toHaveAttribute('data-state', 'error');
    await expect(page.locator('#panorama canvas')).toHaveCount(0);
  }
  const tampered = Buffer.from(jpeg); tampered[500] ^= 1;
  await upload(page, metadata, tampered);
  await expect(status(page)).toContainText('SHA-256');
  const bad = Buffer.from([255, 216, 255, 0, 1, 2]);
  await upload(page, { ...metadata, bytes: bad.length, sha256: createHash('sha256').update(bad).digest('hex') }, bad);
  await expect(status(page)).toContainText('decoding failed');
  await upload(page, { ...metadata, width_px: 768, height_px: 147 });
  await expect(status(page)).toContainText('dimensions');
  await upload(page, metadata);
  await expect(status(page)).toHaveAttribute('data-state', 'ready');
});

test('06 failed example request has an error and can be retried', async ({ page }) => {
  await page.goto('/');
  await page.route('**/fixtures/synthetic.jpg', route => route.fulfill({ status: 404, body: 'missing' }));
  await page.locator('#synthetic').click();
  await expect(status(page)).toContainText('404');
  await page.unroute('**/fixtures/synthetic.jpg');
  await page.locator('#synthetic').click();
  await expect(status(page)).toHaveAttribute('data-state', 'ready');
});

test('07 viewer makes no external requests and server does not expose source photos', async ({ page, request }) => {
  const external = [];
  const origin = new URL(test.info().project.use.baseURL).origin;
  page.on('request', req => { if (!req.url().startsWith(origin + '/') && !req.url().startsWith('blob:')) external.push(req.url()); });
  await load(page, 'synthetic');
  expect(external).toEqual([]);
  for (const path of ['/node_modules/pannellum/package.json', '/serve.mjs', '/../stitch.py', '/samples/room01/01.jpg']) {
    expect((await request.get(path)).status()).toBe(404);
  }
});

test('08 WebGL failure is actionable and does not leave a loaded preview', async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, ...args) {
      return type.includes('webgl') ? null : original.call(this, type, ...args);
    };
  });
  await page.goto('/');
  await page.locator('#synthetic').click();
  await expect(status(page)).toHaveAttribute('data-state', 'error');
  await expect(status(page)).toContainText('WebGL');
  await expect(page.locator('#panorama canvas')).toHaveCount(0);
});
