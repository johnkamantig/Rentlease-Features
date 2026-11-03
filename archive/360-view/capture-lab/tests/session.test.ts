import { test } from 'node:test';
import assert from 'node:assert/strict';
import { progress, makeSession } from '../src/domain';
import { CaptureRepository } from '../src/repository';
import { SessionService } from '../src/sessionService';
import { context, deferred, image, MemoryFiles } from './helpers';

async function started() {
  const files = new MemoryFiles();
  const service = new SessionService(new CaptureRepository(files));
  await service.initialize();
  await service.start(30);
  return { files, service };
}
test('start, pause, resume preserve the active capture set', async () => {
  const { service } = await started();
  const id = service.getSnapshot().session!.id;
  await service.pause();
  assert.equal(service.getSnapshot().session!.status, 'paused');
  await service.resume();
  assert.equal(service.getSnapshot().session!.status, 'active');
  assert.equal(service.getSnapshot().session!.id, id);
});
test('double shutter does not take two photos', async () => {
  const { service } = await started();
  const pending = deferred<typeof image>();
  let calls = 0;
  const first = service.capture('horizontal-0', () => { calls++; return pending.promise; }, context);
  const second = await service.capture('horizontal-0', async () => { calls++; return image; }, context);
  assert.equal(second, false);
  assert.equal(calls, 1);
  pending.resolve(image);
  assert.equal(await first, true);
  assert.equal(progress(service.getSnapshot().session!).captured, 1);
});
test('background interruption during shutter saves any completed photo then pauses', async () => {
  const { service, files } = await started();
  const pending = deferred<typeof image>();
  const capture = service.capture('horizontal-0', () => pending.promise, context);
  await service.pause();
  pending.resolve(image);
  await capture;
  assert.equal(service.getSnapshot().session!.status, 'paused');
  assert.equal(progress(service.getSnapshot().session!).captured, 1);
  const reopened = new SessionService(new CaptureRepository(files));
  await reopened.initialize();
  assert.equal(reopened.getSnapshot().session!.status, 'paused');
  assert.equal(progress(reopened.getSnapshot().session!).captured, 1);
});
test('background interruption during disk copy is also persisted paused', async () => {
  const { service, files } = await started();
  const copying = deferred<void>();
  const entered = deferred<void>();
  const copy = files.copyCapture.bind(files);
  files.copyCapture = async (uri, path) => { entered.resolve(); await copying.promise; await copy(uri, path); };
  const capture = service.capture('horizontal-0', async () => image, context);
  await entered.promise;
  await service.pause();
  copying.resolve();
  await capture;
  assert.equal((await new CaptureRepository(files).restore())!.session.status, 'paused');
  assert.equal(progress(service.getSnapshot().session!).captured, 1);
});
test('shutter failure does not advance progress and permits retry', async () => {
  const { service } = await started();
  assert.equal(await service.capture('horizontal-0', async () => { throw new Error('native camera failure'); }, context), false);
  assert.match(service.getSnapshot().error!, /camera could not/);
  assert.equal(progress(service.getSnapshot().session!).captured, 0);
  assert.equal(service.getSnapshot().busy, false);
  assert.equal(await service.capture('horizontal-0', async () => image, context), true);
});
test('paused sessions cannot invoke the camera', async () => {
  const { service } = await started();
  await service.pause();
  let called = false;
  await service.capture('horizontal-0', async () => { called = true; return image; }, context);
  assert.equal(called, false);
  assert.match(service.getSnapshot().error!, /Resume/);
});
test('failed retake save leaves the current UI record unchanged', async () => {
  const { service, files } = await started();
  await service.capture('horizontal-0', async () => image, context);
  const photo = service.getSnapshot().session!.targets[0]!.photo;
  files.fail = 'write';
  await service.capture('horizontal-0', async () => image, context);
  assert.deepEqual(service.getSnapshot().session!.targets[0]!.photo, photo);
});
test('finish rejects incomplete targets and never calls the set a panorama', async () => {
  const { service } = await started();
  assert.equal(await service.finish(), false);
  assert.equal(service.getSnapshot().session!.coverageValidated, false);
});
test('a fully captured plan can be finished and restored for review', async () => {
  const { service, files } = await started();
  for (const target of service.getSnapshot().session!.targets) {
    assert.equal(await service.capture(target.id, async () => image, context), true);
  }
  assert.equal(await service.finish(), true);
  const restored = (await new CaptureRepository(files).restore())!.session;
  assert.equal(restored.status, 'complete');
  assert.equal(restored.coverageValidated, false);
  assert.equal(progress(restored).captured, 6);
});
test('cancel cleans local records and allows a fresh plan', async () => {
  const { service, files } = await started();
  await service.capture('horizontal-0', async () => image, context);
  const previousId = service.getSnapshot().session!.id;
  assert.equal(await service.discard(), true);
  assert.equal(files.files.size, 0);
  assert.equal(service.getSnapshot().session, null);
  await service.start(20);
  assert.notEqual(service.getSnapshot().session!.id, previousId);
  assert.equal(progress(service.getSnapshot().session!).planned, 9);
});
test('starting over without explicit discard does not replace photos', async () => {
  const { service } = await started();
  const id = service.getSnapshot().session!.id;
  assert.equal(await service.start(20), false);
  assert.equal(service.getSnapshot().session!.id, id);
});
test('invalid camera dimensions do not create a record', async () => {
  const { service } = await started();
  assert.equal(await service.capture('horizontal-0', async () => ({ ...image, width: NaN }), context), false);
  assert.equal(progress(service.getSnapshot().session!).captured, 0);
});

test('120 degree horizontal completion needs no ceiling or floor and persists sweep', async () => {
  const files = new MemoryFiles();
  const service = new SessionService(new CaptureRepository(files));
  await service.initialize();
  await service.start(40, 120);
  for (const target of service.getSnapshot().session!.targets) {
    assert.equal(target.direction, 'horizontal');
    assert.equal(await service.capture(target.id, async () => image, context), true);
  }
  assert.equal(await service.finish(), true);
  const restored = (await new CaptureRepository(files).restore())!.session;
  assert.equal(restored.status, 'complete');
  assert.equal(restored.sweepDegrees, 120);
  assert.equal(progress(restored).captured, 4);
  assert.equal(restored.coverageValidated, false);
});

test('legacy records cannot resume old stages and are not deleted or converted', async () => {
  const files = new MemoryFiles(), repository = new CaptureRepository(files);
  const old = makeSession(30, 'legacy-room');
  delete old.captureMode; delete old.sweepDegrees;
  old.targets.push({id: 'ceiling-0', direction: 'ceiling', yaw: null, elevation: 90, extra: false, photo: null});
  await repository.save(old);
  const service = new SessionService(repository);
  await service.initialize();
  const original = JSON.stringify(service.getSnapshot().session);
  assert.equal(await service.resume(), false);
  assert.equal(await service.addExtra('horizontal-0'), false);
  assert.equal(await service.capture('ceiling-0', async () => { throw new Error('must not call camera'); }, context), false);
  assert.equal(JSON.stringify(service.getSnapshot().session), original);
  assert.ok(files.files.size > 0);
});

test('extra overlap, interruption, recovery and retake preserve horizontal order', async () => {
  const {service, files} = await started();
  await service.capture('horizontal-0', async () => image, context);
  await service.addExtra('horizontal-0');
  const extra = service.getSnapshot().session!.targets[1]!;
  await service.resume();
  await service.capture(extra.id, async () => image, context);
  await service.pause();
  const reopened = new SessionService(new CaptureRepository(files));
  await reopened.initialize();
  const ids = reopened.getSnapshot().session!.targets.map(t => t.id);
  await reopened.resume();
  await reopened.capture(extra.id, async () => image, context);
  assert.deepEqual(reopened.getSnapshot().session!.targets.map(t => t.id), ids);
  assert.equal(progress(reopened.getSnapshot().session!).captured, 2);
  assert.equal(reopened.getSnapshot().session!.targets[1]!.photo!.revision, 2);
});
