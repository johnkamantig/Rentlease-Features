"""Rotation-only OpenCV experiment. No filling, stretching, or synthesized pixels."""
from __future__ import annotations

from datetime import datetime
import io
import math

import cv2 as cv
import numpy as np
from PIL import Image

MAX_JPEG_BYTES = 10 * 1024**2


class StitchError(RuntimeError):
    pass


def working_image(image, max_side=960):
    scale = min(1.0, max_side / max(image.shape[:2]))
    return cv.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)), interpolation=cv.INTER_AREA)


def _components(count, edges):
    remaining, components = set(range(count)), []
    while remaining:
        group, pending = set(), [min(remaining)]
        while pending:
            node = pending.pop()
            if node in group:
                continue
            group.add(node)
            pending.extend(b if a == node else a for a, b in edges if a == node or b == node)
        remaining -= group
        components.append(sorted(group))
    return components


def align(images, report, match_conf=0.65):
    if not 0 < match_conf < 1:
        raise StitchError('Descriptor matching confidence must be between 0 and 1.')
    report['descriptor_match_confidence'] = match_conf
    # Bound CPU use and make RANSAC reproducible on the tested OpenCV build.
    cv.setNumThreads(1)
    cv.setRNGSeed(0)
    finder = cv.SIFT_create(nfeatures=5000)
    features = [cv.detail.computeImageFeatures2(finder, image) for image in images]
    report['keypoints'] = [len(f.keypoints) for f in features]
    report['sharpness_laplacian_variance'] = [round(float(cv.Laplacian(cv.cvtColor(im, cv.COLOR_BGR2GRAY), cv.CV_64F).var()), 2) for im in images]
    if min(report['keypoints']) < 15:
        raise StitchError('At least one photo has too few features. Retake blank, blurred or dark areas with textured overlap.')
    matcher = cv.detail_BestOf2NearestMatcher(False, match_conf)
    try:
        matches = matcher.apply2(features)
    finally:
        matcher.collectGarbage()
    count = len(images)
    edges, diagnostics = [], []
    for i in range(count):
        for j in range(i + 1, count):
            match = matches[i * count + j]
            if match.num_inliers:
                diagnostics.append({'a': i + 1, 'b': j + 1, 'inliers': match.num_inliers, 'confidence': float(match.confidence)})
            if match.confidence >= 1.0 and match.num_inliers >= 15:
                edges.append((i, j))
    report['matches'] = diagnostics
    report['connected_components'] = [[i + 1 for i in group] for group in _components(count, edges)]
    if len(report['connected_components']) != 1:
        raise StitchError('Feature graph is disconnected. No photos will be silently dropped; add textured overlap between the listed groups.')
    ok, cameras = cv.detail_HomographyBasedEstimator().apply(features, matches, None)
    if not ok:
        raise StitchError('OpenCV camera estimation failed.')
    for camera in cameras:
        camera.R = camera.R.astype(np.float32)
    adjuster = cv.detail_BundleAdjusterRay()
    adjuster.setConfThresh(1.0)
    ok, cameras = adjuster.apply(features, matches, cameras)
    if not ok:
        raise StitchError('OpenCV bundle adjustment failed.')
    for camera, image in zip(cameras, images):
        if (not np.isfinite(camera.K()).all() or not np.isfinite(camera.R).all() or
                not 0.15 * max(image.shape[:2]) < camera.focal < 8 * max(image.shape[:2]) or
                abs(np.linalg.det(camera.R) - 1) > .05):
            raise StitchError('Implausible camera calibration; this result is not trustworthy.')
    # Check the final rotation model against real inlier positions, not just homographies.
    errors = []
    for i, j in edges:
        match = matches[i * count + j]
        residuals = []
        for pair, inlier in zip(match.getMatches(), match.getInliers()):
            if not inlier:
                continue
            a = np.array([*features[i].keypoints[pair.queryIdx].pt, 1.0])
            b = np.array([*features[j].keypoints[pair.trainIdx].pt, 1.0])
            ray = cameras[j].R.T @ cameras[i].R @ np.linalg.solve(cameras[i].K(), a)
            projected = cameras[j].K() @ ray
            if projected[2] > 0:
                residuals.append(float(np.linalg.norm(projected[:2] / projected[2] - b[:2])))
        if residuals:
            errors.extend(residuals)
    if not errors:
        raise StitchError('No usable final alignment residuals.')
    report['alignment_error_work_pixels'] = {'median': float(np.median(errors)), 'p95': float(np.percentile(errors, 95)), 'count': len(errors)}
    report['estimated_focals_work_pixels'] = [float(camera.focal) for camera in cameras]
    if np.median(errors) > 4 or np.percentile(errors, 95) > 15:
        raise StitchError('Large final alignment errors: possible parallax, false matches or lens distortion. See report; no panorama accepted.')
    return cameras


def level_from_sensors(cameras, photos, report):
    """Optional global rotation only. Never replace relative feature alignment."""
    estimated, observed = [], []
    for camera, photo in zip(cameras, photos):
        reading = photo.get('orientation')
        if not reading or reading.get('headingDegrees') is None or reading.get('elevationDegrees') is None:
            continue
        try:
            age = abs((datetime.fromisoformat(photo['requestedAt'].replace('Z', '+00:00')) -
                       datetime.fromisoformat(reading['observedAt'].replace('Z', '+00:00'))).total_seconds())
        except (KeyError, TypeError, ValueError):
            continue
        if age > 2:
            continue
        yaw, elevation = np.radians([reading['headingDegrees'], reading['elevationDegrees']])
        estimated.append(camera.R[:, 2])
        observed.append([math.sin(yaw) * math.cos(elevation), -math.sin(elevation), math.cos(yaw) * math.cos(elevation)])
    report['orientation'] = {'usable_readings': len(observed), 'used_for': 'none', 'alignment_validated': False}
    if len(observed) >= 3:
        source, target = np.array(estimated).T, np.array(observed).T
        u, _, vt = np.linalg.svd(target @ source.T)
        rotation = u @ np.diag([1, 1, np.linalg.det(u @ vt)]) @ vt
        errors = np.degrees(np.arccos(np.clip(np.sum((rotation @ source) * target, axis=0), -1, 1)))
        report['orientation']['angular_error_degrees_median'] = float(np.median(errors))
        if np.median(errors) < 15 and np.max(errors) < 30 and np.linalg.matrix_rank(source, tol=.1) >= 2:
            for camera in cameras:
                camera.R = (rotation @ camera.R).astype(np.float32)
            report['orientation']['used_for'] = 'global leveling only; relative rotations remain feature-derived'
            return
    # Full multi-row scenes need not have a dominant horizontal row. Avoid forcing waveCorrect.
    report['warnings'].append('Horizon is not sensor-leveled. Inspect roll and pole orientation manually; target labels were not treated as measured poses.')


def spherical_warp(image, intrinsic, rotation, width):
    """Inverse pinhole projection, longitude [-pi,pi], latitude [pi/2,-pi/2]."""
    height = width // 2
    result = np.zeros((height, width, 3), np.uint8)
    mask = np.zeros((height, width), np.uint8)
    longitude = ((np.arange(width, dtype=np.float32) + .5) / width - .5) * (2 * np.pi)
    sin_lon, cos_lon = np.sin(longitude)[None, :], np.cos(longitude)[None, :]
    for start in range(0, height, 128):
        end = min(start + 128, height)
        latitude = (.5 - (np.arange(start, end, dtype=np.float32) + .5) / height) * np.pi
        cos_lat, sin_lat = np.cos(latitude)[:, None], np.sin(latitude)[:, None]
        world = np.stack(np.broadcast_arrays(sin_lon * cos_lat, -sin_lat, cos_lon * cos_lat), axis=-1)
        camera = world @ rotation
        projected = camera @ intrinsic.T
        z = projected[:, :, 2]
        safe_z = np.where(z > 1e-6, z, 1)
        x = (projected[:, :, 0] / safe_z).astype(np.float32)
        y = (projected[:, :, 1] / safe_z).astype(np.float32)
        valid = (z > 1e-6) & (x >= 1) & (y >= 1) & (x < image.shape[1] - 2) & (y < image.shape[0] - 2)
        warped = cv.remap(image, x, y, cv.INTER_LINEAR, borderMode=cv.BORDER_CONSTANT)
        warped[~valid] = 0
        result[start:end] = warped
        mask[start:end] = valid.astype(np.uint8) * 255
    return result, mask


def coverage_metrics(coverage):
    supported = coverage > 0
    height, width = supported.shape
    weights = np.cos((.5 - (np.arange(height) + .5) / height) * np.pi)[:, None]
    band = max(1, height // 18)  # ten degrees at each pole
    return {'width': width, 'height': height, 'missing_pixels': int((~supported).sum()),
            'supported_fraction_pixels': float(supported.mean()),
            'supported_fraction_solid_angle': float(np.clip((supported * weights).sum() / (width * weights.sum()), 0, 1)),
            'ceiling_10deg_supported_fraction': float(supported[:band].mean()),
            'floor_10deg_supported_fraction': float(supported[-band:].mean()),
            'equator_supported_fraction': float(supported[height // 2].mean()),
            'overlap_fraction': float((coverage > 1).mean()),
            'all_sampled_directions_supported': bool(supported.all()),
            'note': 'Finite-resolution geometric support under estimated pinhole cameras, not proof of correct scene reconstruction.'}


def compose(source, images, cameras, width, report, output):
    if not 512 <= width <= 4096 or width % 2:
        raise StitchError('Output width must be even and between 512 and 4096.')
    coarse_width = 512
    warps, masks = [], []
    for image, camera in zip(images, cameras):
        warped, mask = spherical_warp(image, camera.K(), camera.R, coarse_width)
        warps.append(warped)
        masks.append(mask)
    corners = [(0, 0)] * len(images)
    compensator = cv.detail_GainCompensator()
    compensator.feed(corners, warps, masks)
    report['exposure_gains'] = [float(np.asarray(gain).ravel()[0]) for gain in compensator.getMatGains()]
    for i in range(len(warps)):
        compensator.apply(i, (0, 0), warps[i], masks[i])
    seams = [cv.UMat(mask.copy()) for mask in masks]
    seam_finder = cv.detail_GraphCutSeamFinder('COST_COLOR_GRAD')
    seam_finder.find([im.astype(np.float32) for im in warps], corners, seams)
    seams = [mask.get() for mask in seams]
    # Save coarse ownership visualization, not just a pretty blended result.
    owners = np.zeros((coarse_width // 2, coarse_width, 3), np.uint8)
    for index, seam in enumerate(seams):
        owners[seam > 0] = ((index * 73 + 53) % 256, (index * 139 + 97) % 256, (index * 199 + 29) % 256)
    Image.fromarray(owners).save(output / 'seams.png')
    height = width // 2
    coverage = np.zeros((height, width), np.uint16)
    fallback = np.zeros((height, width, 3), np.uint8)
    # Feather only supported pixels. Multiband filtering of zero-filled warps introduced
    # dark boundary halos in the synthetic experiment; do not extrapolate room content.
    # Wrap padding gives distance-based feather weights continuous seam neighborhoods.
    pad = 64
    blender = cv.detail_FeatherBlender(.04)
    report['blending'] = 'graph-cut seams, 25-pixel feathering with horizontal wrap padding'
    blender.prepare((0, 0, width + 2 * pad, height))
    disagreement_sum, disagreement_count = 0.0, 0
    for i, (photo, camera, work_image) in enumerate(zip(source.manifest['photos'], cameras, images)):
        print(f'Warping {i + 1}/{len(images)}', flush=True)
        image = source.image(photo)
        intrinsic = camera.K().copy()
        intrinsic[0, :] *= image.shape[1] / work_image.shape[1]
        intrinsic[1, :] *= image.shape[0] / work_image.shape[0]
        warped, valid = spherical_warp(image, intrinsic, camera.R, width)
        compensator.apply(i, (0, 0), warped, valid)
        supported = valid > 0
        overlap = supported & (coverage > 0)
        if overlap.any():
            difference = np.abs(warped[overlap].astype(np.float32) - fallback[overlap])
            disagreement_sum += float(difference.sum())
            disagreement_count += difference.size
        fallback[supported & (coverage == 0)] = warped[supported & (coverage == 0)]
        coverage += supported.astype(np.uint16)
        seam = cv.resize(cv.dilate(seams[i], np.ones((3, 3), np.uint8)), (width, height), interpolation=cv.INTER_NEAREST)
        seam &= valid
        padded_image = np.pad(warped, ((0, 0), (pad, pad), (0, 0)), mode='wrap')
        padded_mask = np.pad(seam, ((0, 0), (pad, pad)), mode='wrap')
        blender.feed(padded_image.astype(np.int16), padded_mask, (0, 0))
    blended, blend_mask = blender.blend(None, None)
    result = np.clip(blended[:, pad:pad + width], 0, 255).astype(np.uint8)
    missing_blend = (blend_mask[:, pad:pad + width] == 0) & (coverage > 0)
    result[missing_blend] = fallback[missing_blend]  # Actual source pixels only, no inpainting.
    result[coverage == 0] = 0
    report['blend_fallback_pixels'] = int(missing_blend.sum())
    report['coverage'] = coverage_metrics(coverage)
    report['overlap_mean_absolute_difference_0_255'] = disagreement_sum / max(1, disagreement_count)
    both_edges = (coverage[:, 0] > 0) & (coverage[:, -1] > 0)
    report['wrap_edge_mean_absolute_difference_0_255'] = float(np.abs(result[both_edges, 0].astype(float) - result[both_edges, -1]).mean()) if both_edges.any() else None
    report['warnings'].append('Overlap differences and sharpness scores are heuristic, scene-dependent diagnostics. Inspect seams, poles, straight lines and the wrap boundary.')
    Image.fromarray((coverage > 0).astype(np.uint8) * 255).save(output / 'coverage.png')
    Image.fromarray(np.minimum(coverage * 30, 255).astype(np.uint8)).save(output / 'overlap.png')
    rgba = cv.cvtColor(result, cv.COLOR_BGR2RGBA)
    rgba[:, :, 3] = (coverage > 0).astype(np.uint8) * 255
    Image.fromarray(rgba).save(output / 'diagnostic.png')
    return result


def encode_jpeg(image, limit=MAX_JPEG_BYTES):
    if image.shape[1] != 2 * image.shape[0]:
        raise StitchError('Equirectangular output must be exactly 2:1.')
    if limit <= 0:
        raise StitchError('Invalid JPEG size limit.')
    # Construct from pixels only: no EXIF/GPS/ICC/XMP copied from input files.
    pixels = Image.fromarray(cv.cvtColor(image, cv.COLOR_BGR2RGB))
    for width in (min(4096, pixels.width), 3072, 2048, 1024, 512):
        if width > pixels.width:
            continue
        width -= width % 2
        resized = pixels.resize((width, width // 2), Image.Resampling.LANCZOS)
        for quality in (92, 86, 78, 68, 55):
            buffer = io.BytesIO()
            resized.save(buffer, 'JPEG', quality=quality, optimize=True)
            if buffer.tell() < limit:
                return buffer.getvalue(), {'width': width, 'height': width // 2, 'bytes': buffer.tell(), 'quality': quality, 'metadata_removed': True}
    raise StitchError('Cannot encode JPEG below the configured size limit.')
