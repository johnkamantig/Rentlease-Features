// Only explicit schema fields become viewer options. Never spread input JSON
// into Pannellum config or infer missing angles from the image aspect ratio.
const finite = value => typeof value === 'number' && Number.isFinite(value);
const text = value => typeof value === 'string' && value.trim().length > 0;
const requireValue = (condition, message) => { if (!condition) throw new Error(message); };
export const MAX_IMAGE_BYTES = 9_499_999;
export const MAX_METADATA_BYTES = 512_000;

export function validateMetadata(m, { reference = false } = {}) {
  requireValue(m && typeof m === 'object' && !Array.isArray(m), 'Metadata must be a JSON object.');
  requireValue(m.schema_version === 1, 'Unsupported metadata schema version.');
  requireValue(m.projection === 'partial_equirectangular', 'A calibrated equirectangular image is required.');
  requireValue(m.horizontal_coverage_deg === 360, 'Only verified full 360-degree horizontal coverage is supported.');
  const vaov = m.vertical_coverage_deg, vOffset = m.vertical_offset_deg;
  requireValue(finite(vaov) && vaov >= 20 && vaov <= 180, 'Measured vertical coverage between 20 and 180 degrees is required.');
  requireValue(finite(vOffset), 'Measured vertical offset is required; it cannot be assumed to be zero.');
  requireValue(vOffset - vaov / 2 >= -90 && vOffset + vaov / 2 <= 90, 'Vertical coverage extends beyond the sphere.');
  requireValue(Number.isInteger(m.width_px) && Number.isInteger(m.height_px) &&
    m.width_px >= 512 && m.width_px <= 16384 && m.height_px >= 2 && m.width_px * m.height_px <= 32_000_000,
  'Invalid or oversized image dimensions in metadata.');
  requireValue(Math.abs(m.width_px * vaov / 360 - m.height_px) <= 2, 'Image dimensions disagree with the calibrated equirectangular angles.');
  requireValue(Number.isInteger(m.bytes) && m.bytes > 0 && m.bytes <= MAX_IMAGE_BYTES, 'JPEG must be below 9,500,000 bytes.');
  requireValue(typeof m.sha256 === 'string' && /^[a-f0-9]{64}$/i.test(m.sha256), 'Metadata must contain the JPEG SHA-256.');
  requireValue(text(m.vertical_calibration), 'The vertical calibration description is missing.');
  if (reference) {
    requireValue(m.coverage_validation_status === 'known_reference_geometry' && text(m.reference_source), 'Invalid bundled reference metadata.');
  } else {
    requireValue(m.coverage_validation_status === 'verified_calibrated_rotation_model' && m.closure_verified === true,
      'Panorama coverage and loop closure have not been verified.');
    requireValue(Number.isInteger(m.input_count) && m.input_count >= 6 && m.input_count <= 72, 'Invalid capture input count.');
    const d = m.diagnostics;
    requireValue(d && text(d.calibration_source) && d.calibration_model === 'rectilinear_square_pixels_centered', 'Camera calibration evidence is missing.');
    requireValue(finite(d.raw_turn_deg) && Math.abs(Math.abs(d.raw_turn_deg) - 360) <= 4 &&
      finite(d.raw_closure_error_deg) && d.raw_closure_error_deg >= 0 && d.raw_closure_error_deg <= 3,
    'Metadata does not establish a complete closed revolution.');
    requireValue(m.projection_diagnostics?.source_mask_coverage_fraction === 1, 'Source coverage is incomplete.');
    const seam = m.jpeg_seam_diagnostics;
    requireValue(seam && finite(seam.wrap_mean_absolute_difference) && seam.wrap_mean_absolute_difference >= 0 &&
      finite(seam.wrap_threshold) && seam.wrap_threshold > 0 && seam.wrap_mean_absolute_difference <= seam.wrap_threshold,
    'The encoded JPEG has no passing wrap-seam validation.');
  }
  return Object.freeze({ haov: m.horizontal_coverage_deg, vaov, vOffset, width: m.width_px, height: m.height_px });
}

export async function validateImageBytes(bytes, metadata, cryptoAPI = globalThis.crypto) {
  requireValue(bytes.byteLength === metadata.bytes && bytes.byteLength <= MAX_IMAGE_BYTES, 'Image byte count does not match the metadata.');
  const view = new Uint8Array(bytes);
  requireValue(view[0] === 0xff && view[1] === 0xd8 && view[2] === 0xff, 'The selected image is not a JPEG.');
  requireValue(cryptoAPI?.subtle, 'Integrity checks require localhost or HTTPS. Open the local viewer server.');
  const hash = Array.from(new Uint8Array(await cryptoAPI.subtle.digest('SHA-256', bytes)),
    value => value.toString(16).padStart(2, '0')).join('');
  requireValue(hash === metadata.sha256.toLowerCase(), 'Image SHA-256 does not match the metadata. Choose the matching JPEG and JSON.');
}

export function fovBounds(geometry, width, height) {
  // Reserve a small angular margin for sampling/rounding. This is a viewport
  // limit, not a crop or a change to the calibrated source angles.
  const vertical = Math.min(geometry.vaov - .3, 179);
  const max = Math.min(110, 2 * Math.atan((width / Math.max(1, height)) * Math.tan(vertical * Math.PI / 360)) * 180 / Math.PI);
  return [Math.min(30, max / 2), max];
}

export function viewerConfig(geometry, panorama, width, height) {
  const [minHfov, maxHfov] = fovBounds(geometry, width, height);
  return {
    type: 'equirectangular', panorama,
    haov: geometry.haov, vaov: geometry.vaov, vOffset: geometry.vOffset,
    minPitch: geometry.vOffset - geometry.vaov / 2,
    maxPitch: geometry.vOffset + geometry.vaov / 2,
    pitch: geometry.vOffset, yaw: 0,
    minYaw: -180, maxYaw: 180, // Pannellum's unrestricted full-circle range
    minHfov, maxHfov, hfov: Math.min(90, maxHfov),
    avoidShowingBackground: true, ignoreGPanoXMP: true,
    autoLoad: true, draggable: true, mouseZoom: true, keyboardZoom: true,
    showZoomCtrl: true, showFullscreenCtrl: true, compass: false,
    orientationOnByDefault: false, escapeHTML: true,
  };
}
