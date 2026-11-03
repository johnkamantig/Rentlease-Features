"""Read an export without extracting ZIP paths or changing originals."""
from __future__ import annotations

import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import warnings
import zipfile
import zlib

import cv2 as cv
import numpy as np
from PIL import Image, ImageOps

MAX_PIXELS = 40_000_000
MAX_PHOTO_BYTES = 50 * 1024**2
MAX_TOTAL_BYTES = 2 * 1024**3
MAX_PHOTOS = 300
DIRECTIONS = {'horizontal', 'upper', 'lower', 'ceiling', 'floor'}


class InputError(ValueError):
    pass


def safe_name(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?', name) or '..' in name:
        raise InputError('Unsafe input path in archive or manifest.')
    return name


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def parse_manifest(raw):
    try:
        data = json.loads(raw, object_pairs_hook=_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(InputError('Non-finite JSON value.')))
        if not isinstance(data, dict):
            raise InputError('Manifest must be a JSON object.')
        if type(data['exportVersion']) is not int or data['exportVersion'] != 1 or data['projection'] != 'unstitched-photographs' or data['coverageValidated'] is not False:
            raise InputError('Unsupported capture export version or projection.')
        session, photos = data['session'], data['photos']
        if not isinstance(session, dict) or not isinstance(session.get('targets'), list):
            raise InputError('Invalid session object or targets.')
        if session['schemaVersion'] != 1 or session['status'] != 'complete' or session['coverageValidated'] is not False:
            raise InputError('Export must contain a completed capture set, with coverage still unvalidated.')
        if not isinstance(photos, list) or not 2 <= len(photos) <= MAX_PHOTOS or len(session['targets']) != len(photos):
            raise InputError(f'This experiment accepts 2–{MAX_PHOTOS} photos with matching ordered targets.')
        if 'captureMode' in session or 'sweepDegrees' in session:
            if session.get('captureMode') != 'horizontal' or type(session.get('sweepDegrees')) is not int or session['sweepDegrees'] not in (120, 150, 180):
                raise InputError('Invalid horizontal capture mode or planned sweep.')
            step = session.get('step')
            if type(step) is not int or step not in (15, 20, 30, 40):
                raise InputError('Invalid horizontal photo spacing.')
            targets = session['targets']
            if any(not isinstance(t, dict) or t.get('direction') != 'horizontal' or t.get('elevation') != 0 or
                   type(t.get('extra')) is not bool or (t['extra'] and t.get('yaw') is not None) for t in targets):
                raise InputError('Horizontal capture contains invalid stages or extra targets.')
            expected = list(range(0, session['sweepDegrees'], step)) + [session['sweepDegrees']]
            if [t.get('yaw') for t in targets if not t['extra']] != expected:
                raise InputError('Horizontal capture has missing or unordered planned targets.')
        seen, ids = set(), set()
        for index, (photo, target) in enumerate(zip(photos, session['targets'])):
            if not isinstance(photo, dict) or not isinstance(target, dict):
                raise InputError('Invalid photo or target object.')
            name = safe_name(photo['path'])
            if not name.startswith('images/') or not name.endswith('.jpg') or name in seen:
                raise InputError('Duplicate or invalid JPEG path.')
            seen.add(name)
            if not isinstance(photo['id'], str) or photo['id'] in ids or type(photo['order']) is not int or photo['order'] != index + 1 or photo['targetId'] != target['id']:
                raise InputError('Duplicate photo ID or incorrect photograph order.')
            ids.add(photo['id'])
            if photo['direction'] not in DIRECTIONS or photo['direction'] != target['direction']:
                raise InputError('Invalid capture direction.')
            if photo.get('targetYaw') != target.get('yaw') or photo.get('targetElevation') != target.get('elevation'):
                raise InputError('Photo guide angles disagree with its target.')
            if any(type(photo[k]) is not int or photo[k] <= 0 for k in ('width', 'height', 'bytes')):
                raise InputError('Invalid image dimensions or byte count.')
            if photo['width'] * photo['height'] > MAX_PIXELS or photo['bytes'] > MAX_PHOTO_BYTES:
                raise InputError('Photo exceeds the 40 million pixel / 50 MiB input limit.')
            if not isinstance(photo['crc32'], str) or not re.fullmatch('[0-9a-f]{8}', photo['crc32']):
                raise InputError('Missing or invalid photograph CRC32.')
            if not isinstance(target['photo'], dict) or any(photo.get(k) != value for k, value in target['photo'].items()):
                raise InputError('Export metadata disagrees with the original session snapshot.')
            for key in ('requestedAt', 'savedAt'):
                if not isinstance(photo[key], str) or len(photo[key]) > 40:
                    raise InputError('Invalid photograph timestamp.')
            orientation = photo.get('orientation')
            if orientation is not None:
                if not isinstance(orientation, dict) or orientation.get('alignmentValidated') is not False:
                    raise InputError('Orientation must be explicitly approximate.')
                for key, limit in (('headingDegrees', 360), ('elevationDegrees', 90)):
                    value = orientation.get(key)
                    if value is not None and (type(value) not in (float, int) or not np.isfinite(value) or abs(value) > limit):
                        raise InputError('Invalid orientation angle.')
        if sum(p['bytes'] for p in photos) > MAX_TOTAL_BYTES:
            raise InputError('Capture set exceeds 2 GiB.')
        return data
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeError) as error:
        raise InputError('Malformed capture manifest.') from error


class CaptureInput:
    def __init__(self, path):
        self.path = Path(path).resolve(strict=True)
        self.archive = None
        try:
            if self.path.is_file():
                if self.path.stat().st_size > MAX_TOTAL_BYTES:
                    raise InputError('ZIP exceeds 2 GiB.')
                self.archive = zipfile.ZipFile(self.path)
                infos = self.archive.infolist()
                if len(infos) > 302 or sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
                    raise InputError('Archive has too many entries or is too large.')
                names = set()
                for info in infos:
                    name = safe_name(info.filename)
                    if name in names or info.flag_bits & 1 or stat.S_ISLNK(info.external_attr >> 16):
                        raise InputError('Duplicate, encrypted or linked archive entry.')
                    names.add(name)
                self.names = names
            elif self.path.is_dir():
                self.names = {'manifest.json'}
                folder = self.path / 'images'
                if folder.is_dir():
                    self.names.update(f'images/{p.name}' for p in folder.iterdir() if p.is_file())
            else:
                raise InputError('Choose an exported ZIP or an extracted capture folder.')
            self.manifest = parse_manifest(self.read('manifest.json', 2 * 1024**2))
            required = {p['path'] for p in self.manifest['photos']} | {'manifest.json'}
            if required != self.names:
                raise InputError(f'Image discovery mismatch. Missing: {sorted(required - self.names)}; unexpected: {sorted(self.names - required)}')
        except zipfile.BadZipFile as error:
            self.close()
            raise InputError('Damaged or invalid ZIP archive.') from error
        except Exception:
            self.close()
            raise

    def close(self):
        if self.archive:
            self.archive.close()

    def read(self, name, limit=MAX_PHOTO_BYTES):
        safe_name(name)
        try:
            if self.archive:
                info = self.archive.getinfo(name)
                if info.file_size > limit:
                    raise InputError(f'{name} exceeds its size limit.')
                return self.archive.read(name)  # zipfile also verifies the archive CRC.
            file = self.path.joinpath(*PurePosixPath(name).parts)
            if file.is_symlink() or not file.resolve(strict=True).is_relative_to(self.path):
                raise InputError('Linked or escaping source path.')
            if file.stat().st_size > limit:
                raise InputError(f'{name} exceeds its size limit.')
            return file.read_bytes()
        except (OSError, KeyError, zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error) as error:
            raise InputError(f'Missing or damaged input: {name}') from error

    def image(self, photo):
        name = photo['path']
        raw = self.read(name)
        if len(raw) != photo['bytes'] or f'{zlib.crc32(raw):08x}' != photo['crc32']:
            raise InputError(f'Byte count or CRC mismatch: {name}')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format != 'JPEG' or getattr(image, 'n_frames', 1) != 1:
                        raise InputError(f'Expected a static JPEG: {name}')
                    if image.width * image.height > MAX_PIXELS:
                        raise InputError(f'Decoded image is too large: {name}')
                    if image.size != (photo['width'], photo['height']):
                        raise InputError(f'Dimensions disagree with manifest: {name}')
                    if image.getexif().get(274, 1) != 1:
                        raise InputError(f'Non-normalized EXIF rotation in {name}. Export camera-processed upright JPEGs; do not guess camera alignment.')
                    image.load()  # Strict complete decode, not only headers / verify().
                    rgb = np.asarray(ImageOps.exif_transpose(image).convert('RGB'))
                    return cv.cvtColor(rgb, cv.COLOR_RGB2BGR)
        except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            if isinstance(error, InputError):
                raise
            raise InputError(f'JPEG decoding failed: {name}') from error
