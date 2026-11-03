'use strict';
const el = (id) => document.getElementById(id);
const input = el('imageInput');
const demo = el('demoButton');
const message = el('message');
const shell = el('viewerShell');
let viewer = null;
let cancelLoad = null;
let generation = 0;
let ready = false;
let busy = false;

function setMessage(text, isError = false) {
  message.textContent = text;
  message.classList.toggle('error', isError);
}
function setBusy(value, text = 'Loading panorama...') {
  busy = value;
  input.disabled = demo.disabled = value;
  el('loading').hidden = !value;
  el('loading').textContent = text;
  shell.setAttribute('aria-busy', String(value));
  el('zoomIn').disabled = el('zoomOut').disabled = value || !ready;
}
function destroyViewer() {
  ready = false;
  const previous = viewer;
  viewer = null;
  if (previous) { previous.off(); previous.destroy(); }
  el('panorama').replaceChildren();
}
function displayPanorama(url, label) {
  // Only display server-generated local images, never arbitrary remote URLs.
  if (!/^\/uploads\/(?:[0-9a-f]{32}|demo)\.jpg$/.test(url)) {
    return Promise.reject(new Error('The server returned an invalid panorama URL.'));
  }
  if (!window.pannellum || typeof window.pannellum.viewer !== 'function') {
    return Promise.reject(new Error('The local viewer library is missing. Check static/vendor/pannellum-2.5.7 and restart the server.'));
  }
  if (cancelLoad) cancelLoad();
  const current = ++generation;
  destroyViewer();
  setBusy(true);
  el('viewerName').textContent = 'Loading: ' + label;
  return new Promise((resolve, reject) => {
    let settled = false;
    let candidate;
    let objectURL;
    const controller = new AbortController();
    const finish = (error) => {
      if (settled || current !== generation) return;
      settled = true;
      clearTimeout(timer);
      cancelLoad = null;
      if (objectURL) URL.revokeObjectURL(objectURL);
      if (error) {
        controller.abort();
        destroyViewer();
        el('viewerName').textContent = 'Panorama unavailable';
        reject(error);
      } else {
        ready = true;
        el('viewerName').textContent = label;
        resolve();
      }
      setBusy(false);
    };
    const timer = setTimeout(() => finish(new Error('Viewer loading timed out. Check Wi-Fi, then try the test grid again.')), 30000);
    cancelLoad = () => finish(new Error('Panorama loading was replaced.'));
    async function load() {
      // Own the network request so it can be aborted on timeout / replacement.
      // Pannellum 2.5.7 does not cancel its image XHR in destroy(), and its
      // onloadend handler tries to read a null Blob after a network failure.
      const response = await fetch(url, {signal: controller.signal});
      if (!response.ok) throw new Error('Image request failed');
      const blob = await response.blob();
      if (settled || current !== generation) return;
      objectURL = URL.createObjectURL(blob);
      candidate = window.pannellum.viewer('panorama', {
        type: 'equirectangular', panorama: objectURL, autoLoad: true,
        pitch: 0, yaw: 0, hfov: 100, minHfov: 45, maxHfov: 120,
        showControls: true, showZoomCtrl: false, showFullscreenCtrl: false,
        compass: false, draggable: true, mouseZoom: true, autoRotate: false
      });
      viewer = candidate;
      candidate.on('load', () => finish());
      candidate.on('error', () => finish(new Error('The panorama could not be displayed. Check the local image connection and browser WebGL support, or try a smaller panorama.')));
      if (candidate.isLoaded()) finish();
    }
    load().catch(() => finish(new Error('The panorama could not be displayed. Check the local image connection and browser WebGL support, or try a smaller panorama.')));
  });
}
async function fetchJSON(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch(url, {...options, signal: controller.signal});
    let data;
    try { data = await response.json(); }
    catch { throw new Error('The local server returned an unreadable response. Restart it and try again.'); }
    if (!response.ok) throw new Error(data.error || 'The local server could not complete this request.');
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Request timed out. Check Wi-Fi and try again.');
    if (error instanceof TypeError) throw new Error('Cannot reach the local server. Check Wi-Fi and that server.py is running.');
    throw error;
  } finally { clearTimeout(timer); }
}
input.addEventListener('change', async () => {
  const file = input.files?.[0];
  if (!file || busy) return;
  if (!file.size || file.size > 25 * 1024 * 1024) {
    setMessage('Choose a nonempty image no larger than 25 MiB.', true);
    input.value = '';
    return;
  }
  el('stats').hidden = true;
  setBusy(true, 'Uploading and optimizing locally...');
  setMessage('Uploading and optimizing panorama locally...');
  try {
    const result = await fetchJSON('/api/upload', {
      method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body: file
    });
    if (Math.abs(result.width / result.height - 2) > 0.04) {
      throw new Error('This is not a full-sphere image shape. Open the horizontal panorama viewer for flat pan and zoom.');
    }
    await displayPanorama(result.url, file.name);
    const mib = (bytes) => (bytes / (1024 * 1024)).toFixed(2) + ' MiB';
    const saved = 100 * (1 - result.output_bytes / result.source_bytes);
    el('statsText').replaceChildren();
    for (const text of [
      `Source: ${mib(result.source_bytes)}`,
      `Optimized JPEG: ${mib(result.output_bytes)}`,
      `Output dimensions: ${result.width} x ${result.height}`,
      `Size change: ${saved >= 0 ? saved.toFixed(1) + '% smaller' : Math.abs(saved).toFixed(1) + '% larger'}`
    ]) {
      const p = document.createElement('p');
      p.textContent = text;
      el('statsText').appendChild(p);
    }
    el('stats').hidden = false;
    setMessage('Panorama loaded. Swipe or use arrow keys to explore.');
  } catch (error) {
    setMessage(error.message || 'Could not load the panorama.', true);
  } finally {
    setBusy(false);
    input.value = '';
  }
});
demo.addEventListener('click', async () => {
  if (busy) return;
  el('stats').hidden = true;
  setBusy(true);
  setMessage('Loading the synthetic test grid...');
  try {
    const data = await fetchJSON('/api/demo');
    await displayPanorama(data.url, 'Synthetic 360-degree test grid');
    setMessage('Test grid loaded. Drag or swipe to rotate. This is not a real room image.');
  } catch (error) {
    setMessage(error.message || 'Could not load the test grid.', true);
  } finally { setBusy(false); }
});
el('zoomIn').addEventListener('click', () => { if (ready) viewer.setHfov(viewer.getHfov() - 10); });
el('zoomOut').addEventListener('click', () => { if (ready) viewer.setHfov(viewer.getHfov() + 10); });
function updateFullscreen() {
  const expanded = document.fullscreenElement === shell || shell.classList.contains('expanded');
  el('fullscreenButton').textContent = expanded ? 'Exit fullscreen' : 'Fullscreen';
  el('fullscreenButton').setAttribute('aria-pressed', String(expanded));
  if (viewer) viewer.resize();
}
function setExpanded(expanded) {
  shell.classList.toggle('expanded', expanded);
  document.body.classList.toggle('viewer-expanded', expanded);
  updateFullscreen();
}
el('fullscreenButton').addEventListener('click', async () => {
  if (shell.classList.contains('expanded')) return setExpanded(false);
  if (document.fullscreenElement === shell) {
    try { await document.exitFullscreen(); }
    catch { setMessage('Use the browser Back or Escape control to exit fullscreen.', true); }
    return;
  }
  try {
    if (!shell.requestFullscreen) throw new Error('Fullscreen unavailable');
    await shell.requestFullscreen();
  } catch {
    setExpanded(true);
    setMessage('Expanded view enabled. Use Exit fullscreen or Escape to return.');
  }
});
document.addEventListener('fullscreenchange', updateFullscreen);
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && shell.classList.contains('expanded')) {
    setExpanded(false);
    el('fullscreenButton').focus();
  }
});
