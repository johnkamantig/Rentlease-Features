'use strict';
const el = id => document.getElementById(id);
const viewport = el('viewport'), photo = el('photo'), shell = el('viewerShell');
let zoom = 1, ready = false, busy = false, currentURL = null, request = null;
const pointers = new Map();
let gesture = null;

function message(text, error = false) {
  el('message').textContent = text;
  el('message').classList.toggle('error', error);
}
function setBusy(value) {
  busy = value;
  el('imageInput').disabled = el('demoButton').disabled = value;
  for (const id of ['zoomIn', 'zoomOut', 'fit']) el(id).disabled = value || !ready;
  el('loading').hidden = !value;
  shell.setAttribute('aria-busy', String(value));
}
function layout() {
  if (!ready) return;
  const fit = Math.min(viewport.clientWidth / photo.naturalWidth, viewport.clientHeight / photo.naturalHeight);
  photo.style.width = Math.max(1, photo.naturalWidth * fit * zoom) + 'px';
  photo.style.height = Math.max(1, photo.naturalHeight * fit * zoom) + 'px';
  el('zoomLevel').textContent = `${Math.round(zoom * 100)}% of fit`;
}
function setZoom(value) {
  if (!ready || busy) return;
  const x = (viewport.scrollLeft + viewport.clientWidth / 2) / viewport.scrollWidth;
  const y = (viewport.scrollTop + viewport.clientHeight / 2) / viewport.scrollHeight;
  zoom = Math.min(8, Math.max(1, value));
  layout();
  viewport.scrollLeft = x * viewport.scrollWidth - viewport.clientWidth / 2;
  viewport.scrollTop = y * viewport.scrollHeight - viewport.clientHeight / 2;
}
async function show(endpoint, options, label) {
  if (busy) return;
  setBusy(true);
  message('Loading and optimizing locally…');
  const controller = new AbortController();
  request = controller;
  const timer = setTimeout(() => controller.abort(), 60000);
  let nextURL = null;
  try {
    const response = await fetch(endpoint, {...options, signal: controller.signal});
    let result;
    try { result = await response.json(); } catch { throw new Error('The local server returned an unreadable response.'); }
    if (!response.ok) throw new Error(result.error || 'Local processing failed.');
    if (!/^\/uploads\/(?:[0-9a-f]{32}|demo)\.jpg$/.test(result.url)) throw new Error('The server returned an invalid image URL.');
    const imageResponse = await fetch(result.url, {signal: controller.signal});
    if (!imageResponse.ok) throw new Error('The processed image could not be loaded.');
    nextURL = URL.createObjectURL(await imageResponse.blob());
    const candidate = new Image();
    candidate.src = nextURL;
    await Promise.race([candidate.decode(), new Promise((_, reject) => {
      if (controller.signal.aborted) reject(new Error('Loading timed out.'));
      else controller.signal.addEventListener('abort', () => reject(new Error('Loading timed out.')), {once: true});
    })]);
    if (controller.signal.aborted) throw new Error('Loading timed out.');
    // Keep the previous working image until the replacement has fully decoded.
    photo.src = nextURL;
    await photo.decode();
    if (currentURL) URL.revokeObjectURL(currentURL);
    currentURL = nextURL;
    nextURL = null;
    ready = true;
    zoom = 1;
    photo.hidden = false;
    layout();
    viewport.scrollLeft = viewport.scrollTop = 0;
    el('viewerName').textContent = label;
    el('stats').textContent = `${photo.naturalWidth} × ${photo.naturalHeight}` +
      (result.output_bytes ? ` · ${(result.output_bytes / 1048576).toFixed(2)} MiB JPEG` : ' · synthetic test image');
    message('Image loaded. Pan and zoom to inspect joins, sharpness and missing areas.');
  } catch (error) {
    message(controller.signal.aborted ? 'Loading timed out. Check the local server and Wi-Fi.' :
      (error instanceof TypeError ? 'Cannot reach the local server. Check Wi-Fi and server.py.' : error.message || 'Could not display the image.'), true);
  } finally {
    clearTimeout(timer);
    if (nextURL) URL.revokeObjectURL(nextURL);
    request = null;
    setBusy(false);
    el('imageInput').value = '';
  }
}
el('imageInput').addEventListener('change', () => {
  const file = el('imageInput').files?.[0];
  if (!file || busy) return;
  if (!file.size || file.size > 25 * 1048576) {
    message('Choose a nonempty image no larger than 25 MiB.', true);
    el('imageInput').value = '';
    return;
  }
  void show('/api/upload', {method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body: file}, file.name);
});
el('demoButton').addEventListener('click', () => void show('/api/demo', {}, 'Synthetic test image — not a room panorama'));
el('zoomIn').addEventListener('click', () => setZoom(zoom * 1.5));
el('zoomOut').addEventListener('click', () => setZoom(zoom / 1.5));
el('fit').addEventListener('click', () => setZoom(1));
viewport.addEventListener('keydown', event => {
  if (!ready || busy) return;
  const delta = {ArrowLeft: [-80, 0], ArrowRight: [80, 0], ArrowUp: [0, -80], ArrowDown: [0, 80]}[event.key];
  if (delta) viewport.scrollBy(...delta);
  else if (event.key === '+' || event.key === '=') setZoom(zoom * 1.5);
  else if (event.key === '-') setZoom(zoom / 1.5);
  else if (event.key === '0') setZoom(1);
  else return;
  event.preventDefault();
});
function resetGesture() {
  const points = [...pointers.values()];
  gesture = points.length === 1 ? {x: points[0].x, y: points[0].y, left: viewport.scrollLeft, top: viewport.scrollTop} :
    points.length === 2 ? {distance: Math.hypot(points[1].x - points[0].x, points[1].y - points[0].y), zoom} : null;
}
viewport.addEventListener('pointerdown', event => {
  if (!ready || busy || (event.pointerType === 'mouse' && event.button !== 0)) return;
  viewport.focus({preventScroll: true});
  viewport.setPointerCapture(event.pointerId);
  pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
  resetGesture();
});
viewport.addEventListener('pointermove', event => {
  if (!pointers.has(event.pointerId) || !gesture) return;
  pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
  if (pointers.size === 1) {
    viewport.scrollLeft = gesture.left + gesture.x - event.clientX;
    viewport.scrollTop = gesture.top + gesture.y - event.clientY;
  } else if (pointers.size === 2 && gesture.distance > 0) {
    const [a, b] = [...pointers.values()];
    setZoom(gesture.zoom * Math.hypot(b.x - a.x, b.y - a.y) / gesture.distance);
  }
});
for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) viewport.addEventListener(event, e => {
  pointers.delete(e.pointerId);
  resetGesture();
});
function fullscreenState() {
  const expanded = document.fullscreenElement === shell || shell.classList.contains('expanded');
  el('fullscreenButton').textContent = expanded ? 'Exit fullscreen' : 'Fullscreen';
  el('fullscreenButton').setAttribute('aria-pressed', String(expanded));
  layout();
}
function expand(value) {
  shell.classList.toggle('expanded', value);
  document.body.classList.toggle('expanded', value);
  fullscreenState();
}
el('fullscreenButton').addEventListener('click', async () => {
  if (shell.classList.contains('expanded')) return expand(false);
  try {
    if (document.fullscreenElement === shell) await document.exitFullscreen();
    else if (shell.requestFullscreen) await shell.requestFullscreen();
    else expand(true);
  } catch {
    if (document.fullscreenElement === shell) message('Use Escape or the browser control to exit fullscreen.', true);
    else expand(true);
  }
});
document.addEventListener('fullscreenchange', fullscreenState);
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && shell.classList.contains('expanded')) {
    expand(false);
    el('fullscreenButton').focus();
  }
});
new ResizeObserver(layout).observe(viewport);
window.addEventListener('pagehide', () => { request?.abort(); if (currentURL) URL.revokeObjectURL(currentURL); });
