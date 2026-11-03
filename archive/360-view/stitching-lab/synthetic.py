"""Deterministic pinhole views of a synthetic textured sphere; NOT a real-room test."""
import argparse
import json
from pathlib import Path
import zlib

import cv2 as cv
import numpy as np
from PIL import Image


def rotation(yaw, elevation):
    yaw, elevation = np.radians([yaw, elevation])
    forward = np.array([np.sin(yaw) * np.cos(elevation), -np.sin(elevation), np.cos(yaw) * np.cos(elevation)])
    right = np.array([np.cos(yaw), 0, -np.sin(yaw)])
    down = np.cross(forward, right)
    return np.column_stack([right, down, forward]).astype(np.float32)


def render(texture, intrinsic, camera_to_world, width, height):
    y, x = np.mgrid[:height, :width].astype(np.float32)
    rays = np.stack([x, y, np.ones_like(x)], axis=-1) @ np.linalg.inv(intrinsic).T @ camera_to_world.T
    rays /= np.linalg.norm(rays, axis=-1, keepdims=True)
    longitude = np.arctan2(rays[:, :, 0], rays[:, :, 2])
    latitude = np.arcsin(-rays[:, :, 1])
    map_x = ((longitude / (2 * np.pi) + .5) * texture.shape[1] - .5).astype(np.float32)
    map_y = ((.5 - latitude / np.pi) * texture.shape[0] - .5).astype(np.float32)
    return cv.remap(texture, map_x, map_y, cv.INTER_LINEAR, borderMode=cv.BORDER_WRAP)


def create_fixture(path, partial=False, width=480, height=360):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    (path / 'images').mkdir()
    rng = np.random.default_rng(2026)
    texture = rng.integers(30, 225, (1024, 2048, 3), dtype=np.uint8)
    texture = cv.GaussianBlur(texture, (5, 5), 0)
    for _ in range(3500):
        x, y = rng.integers([0, 0], [2048, 1024])
        color = tuple(int(c) for c in rng.integers(10, 245, 3))
        cv.circle(texture, (int(x), int(y)), int(rng.integers(2, 12)), color, -1)
    for row in range(8):
        for col in range(16):
            cv.putText(texture, f'{row}:{col}', (col * 128 + 8, row * 128 + 65), cv.FONT_HERSHEY_SIMPLEX, .7, (245, 245, 245), 2)
    focal = width / (2 * np.tan(np.radians(90) / 2))
    intrinsic = np.array([[focal, 0, width / 2], [0, focal, height / 2], [0, 0, 1]], np.float32)
    views = [(yaw, elevation, direction) for elevation, direction in [(0, 'horizontal'), (45, 'upper'), (-45, 'lower')]
             for yaw in range(0, 360, 45)] + [(0, 90, 'ceiling'), (0, -90, 'floor')]
    if partial:
        views = views[:4]
    timestamp = '2026-10-27T08:00:00.000Z'
    photos, targets, truth = [], [], []
    for i, (yaw, elevation, direction) in enumerate(views):
        matrix = rotation(yaw, elevation)
        image = render(texture, intrinsic, matrix, width, height)
        filename = f'photo-synthetic-{i:03}.jpg'
        name = f'images/{i + 1:04}-{filename}'
        Image.fromarray(cv.cvtColor(image, cv.COLOR_BGR2RGB)).save(path / name, quality=96)
        raw = (path / name).read_bytes()
        photo = {'id': filename[:-4], 'filename': filename, 'width': width, 'height': height,
                 'requestedAt': timestamp, 'savedAt': timestamp, 'direction': direction,
                 'targetYaw': yaw if abs(elevation) < 90 else None, 'targetElevation': elevation,
                 'orientation': {'observedAt': timestamp, 'headingDegrees': yaw, 'elevationDegrees': elevation,
                                 'acceleration': None, 'magneticField': None, 'source': 'accelerometer+magnetometer', 'alignmentValidated': False},
                 'referenceHeading': 0, 'referenceSetAt': timestamp, 'revision': 1}
        target_id = f'{direction}-{i}'
        targets.append({'id': target_id, 'direction': direction, 'yaw': photo['targetYaw'], 'elevation': elevation, 'extra': False, 'photo': photo})
        photos.append({'order': i + 1, 'targetId': target_id, 'path': name, **photo, 'bytes': len(raw), 'crc32': f'{zlib.crc32(raw):08x}'})
        truth.append({'K': intrinsic.tolist(), 'R': matrix.tolist()})
    manifest = {'exportVersion': 1, 'exportedAt': timestamp, 'projection': 'unstitched-photographs', 'coverageValidated': False,
                'session': {'schemaVersion': 1, 'id': 'synthetic-fixture', 'revision': 1, 'createdAt': timestamp, 'updatedAt': timestamp,
                            'status': 'complete', 'step': 30, 'targets': targets, 'coverageValidated': False}, 'photos': photos,
                'notes': 'SYNTHETIC ONLY. Known central pinhole views; no parallax, distortion, motion or sensor error.'}
    (path / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return texture, truth


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--partial', action='store_true')
    args = parser.parse_args()
    create_fixture(args.output, args.partial)
