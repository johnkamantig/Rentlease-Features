import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { CaptureRepository, type LocalFiles } from '../src/repository';
import { makeSession } from '../src/domain';
import { localPath, isCameraCacheUri } from '../src/localPaths';
import { context, image } from './helpers';

test('capture paths reject traversal, absolute paths, nested escapes and Windows separators', () => {
  for (const candidate of ['../outside', '/outside', 'C:\\outside', 'room/../file', 'room/..', 'room/.', 'room\\photo.jpg', 'room/%2e%2e', 'room/photo.jpg:stream', 'room/a/b']) {
    assert.throws(() => localPath(candidate), candidate);
  }
  assert.equal(localPath('room-1/photo-1.jpg'), 'room-1/photo-1.jpg');
  assert.equal(localPath('room-1/manifest-0000001.json.tmp'), 'room-1/manifest-0000001.json.tmp');
});
test('camera temporary-file cleanup is restricted to the camera cache subtree', () => {
  const root = 'file:///app/cache/';
  assert.ok(isCameraCacheUri('file:///app/cache/Camera/photo.jpg', root));
  for (const uri of ['file:///app/cache-other/photo.jpg', 'file:///app/cache/../document/photo.jpg', 'file:///app/cache/%2e%2e/photo.jpg', 'content://photos/1', 'https://example.com/photo.jpg']) {
    assert.equal(isCameraCacheUri(uri, root), false, uri);
  }
});

test('Expo Go percent-encoded experience directories accept their own camera photos', () => {
  const root = 'file:///data/user/0/host.exp.exponent/cache/ExperienceData/%2540anonymous%252Frentlease-capture-lab/';
  assert.ok(isCameraCacheUri(root + 'Camera/photo.jpg', root));
  assert.equal(isCameraCacheUri(root.replace('rentlease-capture-lab', 'another-project') + 'Camera/photo.jpg', root), false);
});

test('equivalent local file URI spellings compare by decoded path segments', () => {
  assert.ok(isCameraCacheUri('file:/app/cache/Camera/photo.jpg', 'file:///app/cache/'));
  assert.ok(isCameraCacheUri('file:///app/cache/room%20one/Camera/photo.jpg', 'file:/app/cache/room one/'));
  assert.ok(isCameraCacheUri('file:///app/cache/%40owner/Camera/photo.jpg', 'file:///app/cache/@owner/'));
  assert.ok(isCameraCacheUri('file:///app/cache/room..one/Camera/photo.jpg', 'file:///app/cache/room..one/'));
});

test('URI decoding never permits traversal, separators, remote hosts or malformed input', () => {
  const root = 'file:///app/cache/';
  for (const suffix of [
    '%2e%2e/document/photo.jpg', '.%2e/document/photo.jpg', '%252e%252e/photo.jpg',
    'Camera%2f..%2f..%2fdocument/photo.jpg', 'Camera%5c..%5cphoto.jpg',
    'Camera/%00photo.jpg', 'Camera/%ZZ.jpg', 'Camera/photo.jpg?other=1', 'Camera/photo.jpg#part',
  ]) assert.equal(isCameraCacheUri(root + suffix, root), false, suffix);
  for (const uri of ['file://other-host/app/cache/Camera/photo.jpg', '/app/cache/Camera/photo.jpg', root, root + '../cache/Camera/photo.jpg']) {
    assert.equal(isCameraCacheUri(uri, root), false, uri);
  }
  assert.equal(isCameraCacheUri(root + 'Camera/photo.jpg', 'file:///'), false);
});

test('encoded Expo project IDs are decoded exactly once, not into a different directory', () => {
  const root = 'file:///app/cache/ExperienceData/%2540owner%252Fproject/';
  assert.ok(isCameraCacheUri(root + 'Camera/photo.jpg', root));
  assert.equal(isCameraCacheUri('file:///app/cache/ExperienceData/%40owner%2Fproject/Camera/photo.jpg', root), false);
});

test('repository data survives disk reopen and scoped discard on a real filesystem', async () => {
  const temporaryRoot = path.resolve('.tmp');
  await fs.mkdir(temporaryRoot, { recursive: true });
  const directory = await fs.mkdtemp(path.join(temporaryRoot, 'capture-test-'));
  const resolved = path.resolve(directory);
  assert.ok(resolved.startsWith(temporaryRoot + path.sep));
  const full = (relative: string) => path.join(directory, localPath(relative));
  const files: LocalFiles = {
    async mkdir(relative) { await fs.mkdir(full(relative), { recursive: true }); },
    async list(relative) { return fs.readdir(full(relative)); },
    async exists(relative) { try { return (await fs.stat(full(relative))).isFile(); } catch { return false; } },
    async read(relative) { return fs.readFile(full(relative), 'utf8'); },
    async write(relative, content) { await fs.writeFile(full(relative), content); },
    async move(from, to) { await fs.rename(full(from), full(to)); },
    async copyCapture(_uri, to) { await fs.writeFile(full(to), 'fixture image bytes'); },
    async remove(relative) {
      const target = path.resolve(full(relative));
      assert.ok(target.startsWith(resolved + path.sep));
      await fs.rm(target, { recursive: true, force: true });
    },
    uri(relative) { return pathToFileURL(full(relative)).href; },
  };
  try {
    const repository = new CaptureRepository(files);
    const started = await repository.save(makeSession(30, 'disk-room'));
    const saved = await repository.savePhoto(started.session, 'horizontal-0', image, context);
    const reopened = await new CaptureRepository(files).restore();
    assert.equal(reopened!.session.targets[0]!.photo!.filename, saved.session.targets[0]!.photo!.filename);
    assert.equal(await fs.readFile(full(`disk-room/${saved.session.targets[0]!.photo!.filename}`), 'utf8'), 'fixture image bytes');
    await repository.discardAll();
    assert.deepEqual(await files.list(''), []);
  } finally {
    assert.ok(path.resolve(directory).startsWith(temporaryRoot + path.sep));
    await fs.rm(directory, { recursive: true, force: true });
  }
});
