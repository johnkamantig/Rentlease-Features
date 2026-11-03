import { validateMetadata, validateImageBytes, viewerConfig, fovBounds, MAX_IMAGE_BYTES, MAX_METADATA_BYTES } from './metadata.mjs';

const container = document.querySelector('#panorama');
const status = document.querySelector('#status');
let viewer, imageURL, geometry, generation = 0, timer;
const TIMEOUT_MS = 20000;

function message(state, text) {
  status.dataset.state = state;
  status.textContent = text;
  container.setAttribute('aria-busy', String(state === 'loading'));
}

function clearViewer() {
  clearTimeout(timer);
  if (viewer) viewer.destroy();
  viewer = undefined;
  geometry = undefined;
  if (imageURL) URL.revokeObjectURL(imageURL);
  imageURL = undefined;
  container.replaceChildren();
}

async function openPanorama(read, { reference = false, name = 'Panorama' } = {}) {
  const token = ++generation;
  clearViewer();
  message('loading', 'Loading and validating panorama...');
  const fail = error => {
    if (token !== generation) return;
    ++generation; // Ignore callbacks or reads that finish after failure/timeout.
    clearViewer();
    message('error', error.message || 'Unable to load this panorama.');
  };
  timer = setTimeout(() => fail(new Error('Panorama loading timed out. Try again.')), TIMEOUT_MS);
  try {
    const { metadata, bytes } = await read();
    if (token !== generation) return;
    const checked = validateMetadata(metadata, { reference });
    await validateImageBytes(bytes, metadata);
    if (token !== generation) return;
    imageURL = URL.createObjectURL(new Blob([bytes], { type: 'image/jpeg' }));
    const image = new Image();
    image.src = imageURL;
    try { await image.decode(); } catch { throw new Error('JPEG decoding failed. The image is corrupt or unsupported.'); }
    if (token !== generation) return;
    if (image.naturalWidth !== checked.width || image.naturalHeight !== checked.height) {
      throw new Error('Decoded image dimensions do not match the metadata.');
    }
    if (!window.pannellum) throw new Error('Pannellum could not load. Check the local vendor files.');
    geometry = checked;
    viewer = window.pannellum.viewer(container, viewerConfig(geometry, imageURL, container.clientWidth, container.clientHeight));
    viewer.on('load', () => {
      if (token !== generation) return;
      clearTimeout(timer);
      fitViewport();
      message('ready', `${name} loaded. Horizontal: ${geometry.haov}°, vertical: ${geometry.vaov.toFixed(2)}°. Drag to look around.`);
    });
    viewer.on('error', () => fail(new Error('The 360 viewer could not render this image. Check WebGL support and image size.')));
  } catch (error) { fail(error); }
}

function fitViewport() {
  if (!viewer || !geometry) return;
  const bounds = fovBounds(geometry, container.clientWidth, container.clientHeight);
  viewer.setHfovBounds(bounds);
  viewer.resize();
  viewer.setHfov(Math.max(bounds[0], Math.min(bounds[1], viewer.getHfov())), false);
}
new ResizeObserver(fitViewport).observe(container);

async function localAsset(url, limit) {
  const response = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT_MS) });
  if (!response.ok) throw new Error(`Could not load local example (${response.status}).`);
  const blob = await response.blob();
  if (blob.size > limit) throw new Error('Example file exceeds the size limit.');
  return blob;
}

function example(key) {
  return openPanorama(async () => {
    const [image, json] = await Promise.all([
      localAsset(`fixtures/${key}.jpg`, MAX_IMAGE_BYTES), localAsset(`fixtures/${key}.json`, MAX_METADATA_BYTES),
    ]);
    return { metadata: JSON.parse(await json.text()), bytes: await image.arrayBuffer() };
  }, { reference: key === 'reference', name: key === 'reference' ? 'Reference sphere (synthetic)' : 'Phase 2 synthetic panorama' });
}
document.querySelector('#reference').addEventListener('click', () => example('reference'));
document.querySelector('#synthetic').addEventListener('click', () => example('synthetic'));
document.querySelector('#open-files').addEventListener('submit', event => {
  event.preventDefault();
  const image = document.querySelector('#image-file').files[0];
  const json = document.querySelector('#metadata-file').files[0];
  openPanorama(async () => {
    if (!image || !json) throw new Error('Choose both a JPEG and its metadata JSON.');
    if (image.size > MAX_IMAGE_BYTES || json.size > MAX_METADATA_BYTES) throw new Error('Selected file exceeds the size limit.');
    let metadata;
    try { metadata = JSON.parse(await json.text()); } catch { throw new Error('The metadata file is not valid JSON.'); }
    return { metadata, bytes: await image.arrayBuffer() };
  });
});

// Read-only diagnostic access for browser QA; uploads still use the real form.
export function currentViewer() { return viewer; }
window.addEventListener('pagehide', () => { ++generation; clearViewer(); });
