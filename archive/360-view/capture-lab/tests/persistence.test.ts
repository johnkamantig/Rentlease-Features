import { test } from 'node:test';
import assert from 'node:assert/strict';
import { makeSession, progress } from '../src/domain';
import { CaptureRepository } from '../src/repository';
import { context, image, MemoryFiles } from './helpers';

async function savedPhoto() {
  const files = new MemoryFiles();
  const repository = new CaptureRepository(files);
  const started = await repository.save(makeSession(30, 'test-room'));
  const saved = await repository.savePhoto(started.session, 'horizontal-0', image, context);
  return { files, repository, saved };
}
test('photo and ordered metadata survive a fresh repository instance', async () => {
  const { files, saved } = await savedPhoto();
  const restored = await new CaptureRepository(files).restore();
  assert.equal(restored!.session.id, saved.session.id);
  assert.equal(restored!.session.status, 'paused');
  assert.equal(progress(restored!.session).captured, 1);
  const photo = restored!.session.targets[0]!.photo!;
  assert.equal(photo.width, 3000);
  assert.equal(photo.height, 4000);
  assert.equal(photo.requestedAt, context.requestedAt);
  assert.equal(photo.direction, 'horizontal');
  assert.ok(files.files.has(`test-room/${photo.filename}`));
});
test('failed retake copy keeps original record and photo', async () => {
  const { files, repository, saved } = await savedPhoto();
  files.fail = 'copy';
  await assert.rejects(repository.savePhoto(saved.session, 'horizontal-0', image, context));
  assert.equal((await repository.restore())!.session.targets[0]!.photo!.filename, saved.session.targets[0]!.photo!.filename);
  assert.equal([...files.files.keys()].filter(p => p.endsWith('.jpg')).length, 1);
});
test('failed manifest write keeps original retake and removes partial files', async () => {
  const { files, repository, saved } = await savedPhoto();
  files.fail = 'write';
  await assert.rejects(repository.savePhoto(saved.session, 'horizontal-0', image, context), /previous save/);
  files.fail = null;
  assert.equal((await repository.restore())!.session.targets[0]!.photo!.id, saved.session.targets[0]!.photo!.id);
  assert.equal([...files.files.keys()].filter(p => p.endsWith('.jpg')).length, 1);
  assert.equal([...files.files.keys()].filter(p => p.endsWith('.tmp')).length, 0);
});
test('failed snapshot publication never replaces the previous committed record', async () => {
  const { files, repository, saved } = await savedPhoto();
  files.fail = 'move';
  await assert.rejects(repository.save({ ...saved.session, status: 'paused' }));
  files.fail = null;
  assert.equal((await repository.restore())!.session.revision, saved.session.revision);
});
test('successful retake retains one backup snapshot and referenced old photo', async () => {
  const { files, repository, saved } = await savedPhoto();
  const old = saved.session.targets[0]!.photo!;
  const retaken = await repository.savePhoto(saved.session, 'horizontal-0', image, context);
  const replacement = retaken.session.targets[0]!.photo!;
  assert.notEqual(old.id, replacement.id);
  assert.equal(replacement.revision, 2);
  assert.equal(progress(retaken.session).captured, 1);
  assert.ok(files.files.has(`test-room/${old.filename}`));
  await repository.save({ ...retaken.session, status: 'paused' });
  assert.ok(!files.files.has(`test-room/${old.filename}`));
  assert.ok(files.files.has(`test-room/${replacement.filename}`));
});
test('corrupt latest snapshot falls back and can subsequently save with a new revision', async () => {
  const { files, repository, saved } = await savedPhoto();
  const recent = await repository.save(saved.session);
  const name = `test-room/manifest-${String(recent.session.revision).padStart(7, '0')}.json`;
  files.files.set(name, '{truncated');
  const restored = (await repository.restore())!;
  assert.match(restored.warning!, /earlier save/);
  assert.equal(progress(restored.session).captured, 1);
  const recovered = await repository.save(restored.session);
  assert.ok(recovered.session.revision > recent.session.revision);
});
test('unpublished temporary snapshot is ignored', async () => {
  const { files, repository, saved } = await savedPhoto();
  files.files.set('test-room/manifest-9999999.json.tmp', '{not committed');
  assert.equal((await repository.restore())!.session.revision, saved.session.revision);
});
test('missing photo returns target to incomplete and warns', async () => {
  const { files, repository, saved } = await savedPhoto();
  files.files.delete(`test-room/${saved.session.targets[0]!.photo!.filename}`);
  const recovered = (await repository.restore())!;
  assert.equal(progress(recovered.session).captured, 0);
  assert.equal(recovered.session.status, 'paused');
  assert.match(recovered.warning!, /missing/);
});
test('unreadable records are preserved until explicit discard', async () => {
  const files = new MemoryFiles();
  const repository = new CaptureRepository(files);
  await files.mkdir('broken-room');
  files.files.set('broken-room/manifest-0000001.json', '{}');
  files.files.set('broken-room/photo-old.jpg', 'important photo');
  await assert.rejects(repository.restore(), /no capture record/);
  assert.ok(files.files.has('broken-room/photo-old.jpg'));
  await repository.discardAll();
  assert.equal(await repository.restore(), null);
  assert.equal(files.files.size, 0);
});
test('cleanup failure is a warning, not a failed photo transaction', async () => {
  const { files, repository, saved } = await savedPhoto();
  files.fail = 'remove';
  const result = await repository.savePhoto(saved.session, 'horizontal-0', image, context);
  assert.match(result.warning!, /Saved/);
  assert.ok(files.files.has(`test-room/${result.session.targets[0]!.photo!.filename}`));
});
test('orphan camera copies are removed after a successful commit', async () => {
  const { files, repository, saved } = await savedPhoto();
  files.files.set('test-room/photo-orphan.jpg', 'unreferenced');
  await repository.save(saved.session);
  assert.ok(!files.files.has('test-room/photo-orphan.jpg'));
});
