import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DIRECTIONS, insertExtra, makeSession, nextTarget, parseSession, progress, replacePhoto, type Photo } from '../src/domain';
import { context } from './helpers';

test('horizontal plan has only level targets and includes the end of the sweep', () => {
  const session = makeSession(30, 'test-room');
  assert.deepEqual([...new Set(session.targets.map(t => t.direction))], ['horizontal']);
  assert.deepEqual(session.targets.map(t => t.yaw), [0, 30, 60, 90, 120, 150]);
  assert.ok(session.targets.every(t => t.elevation === 0));
  assert.equal(session.captureMode, 'horizontal');
  assert.equal(session.coverageValidated, false);
});
test('spacing and sweep change counts without claiming verified coverage', () => {
  assert.equal(makeSession(15).targets.length, 11);
  assert.equal(makeSession(20).targets.length, 9);
  assert.deepEqual(makeSession(40).targets.map(t => t.yaw), [0, 40, 80, 120, 150]);
  for (const sweep of [120, 150, 180] as const) {
    assert.equal(makeSession(20, undefined, undefined, sweep).targets.at(-1)!.yaw, sweep);
  }
  assert.throws(() => makeSession(20, undefined, undefined, 360 as 180));
});
test('unsupported spacing is rejected', () => {
  assert.throws(() => makeSession(0 as 30));
});
test('extra shot is inserted beside selected target without reordering existing IDs', () => {
  const before = makeSession(30);
  const after = insertExtra(before, before.targets[1]!.id, 'extra-test');
  assert.equal(after.targets[2]!.id, 'extra-test');
  assert.equal(after.targets[2]!.direction, 'horizontal');
  assert.equal(after.targets[2]!.yaw, null);
  assert.deepEqual(after.targets.filter(t => !t.extra).map(t => t.id), before.targets.map(t => t.id));
  assert.equal(before.targets.length, 6);
  assert.equal(progress(after).planned, 7);
});
test('legacy records remain readable without being converted to horizontal capture', () => {
  const session = makeSession(40);
  delete session.captureMode; delete session.sweepDegrees;
  session.targets.push({ id: 'ceiling-0', direction: 'ceiling', yaw: null, elevation: 90, extra: false, photo: null });
  session.revision = 1;
  const restored = parseSession(JSON.stringify(session));
  assert.equal(restored.targets.at(-1)!.direction, 'ceiling');
  assert.equal(restored.captureMode, undefined);
});
test('horizontal metadata cannot hide nonhorizontal or missing planned targets', () => {
  const session = { ...makeSession(20), revision: 1 };
  const wrongStage = structuredClone(session); wrongStage.targets[0]!.direction = 'upper';
  assert.throws(() => parseSession(JSON.stringify(wrongStage)));
  const missing = structuredClone(session); missing.targets.pop();
  assert.throws(() => parseSession(JSON.stringify(missing)));
  assert.throws(() => parseSession(JSON.stringify({ ...session, sweepDegrees: 360 })));
});

function samplePhoto(): Photo {
  return { id: 'photo-test', filename: 'photo-test.jpg', width: 3000, height: 4000, ...context,
    savedAt: context.requestedAt, direction: 'horizontal', targetYaw: 0, targetElevation: 0, revision: 1 };
}
test('progress and next target advance only for saved photos and wrap to earlier gaps', () => {
  const session = makeSession(30);
  const first = session.targets[0]!;
  const saved = replacePhoto(session, first.id, samplePhoto());
  assert.deepEqual(progress(saved), { captured: 1, planned: 6, remaining: 5 });
  assert.equal(nextTarget(saved, first.id)!.id, saved.targets[1]!.id);
  assert.equal(nextTarget(saved, saved.targets.at(-1)!.id)!.id, saved.targets[1]!.id);
  assert.equal(progress(session).captured, 0);
});
test('retake retains order and does not increment captured count', () => {
  const session = makeSession(30);
  const first = replacePhoto(session, session.targets[0]!.id, samplePhoto());
  const second = replacePhoto(first, first.targets[0]!.id, { ...samplePhoto(), id: 'photo-new', filename: 'photo-new.jpg', revision: 2 });
  assert.equal(progress(second).captured, 1);
  assert.deepEqual(second.targets.map(t => t.id), session.targets.map(t => t.id));
  assert.equal(second.targets[0]!.photo!.revision, 2);
});
test('wrong direction and missing target cannot receive a photo', () => {
  const session = makeSession(30);
  assert.throws(() => replacePhoto(session, 'missing', samplePhoto()));
  assert.throws(() => replacePhoto(session, 'floor-0', samplePhoto()));
});
test('persisted metadata round-trips without absolute file paths', () => {
  const session = { ...replacePhoto(makeSession(30), 'horizontal-0', samplePhoto()), revision: 1 };
  assert.deepEqual(parseSession(JSON.stringify(session)), session);
  assert.ok(!JSON.stringify(session).includes('file://'));
});
test('persisted traversal, invalid schemas, duplicate IDs, and invalid dimensions are rejected', () => {
  const session = { ...replacePhoto(makeSession(30), 'horizontal-0', samplePhoto()), revision: 1 };
  const mutations = [
    (s: typeof session) => { s.id = '../private'; },
    (s: typeof session) => { s.targets[0]!.photo!.filename = '../../secret.jpg'; },
    (s: typeof session) => { s.targets[0]!.photo!.width = -1; },
    (s: typeof session) => { s.targets[1]!.id = s.targets[0]!.id; },
    (s: typeof session) => { s.targets[0]!.yaw = 999; },
    (s: typeof session) => { s.createdAt = 'invalid'; },
    (s: typeof session) => { s.schemaVersion = 2 as 1; },
    (s: typeof session) => { s.coverageValidated = true as false; },
  ];
  for (const mutate of mutations) {
    const copy = structuredClone(session);
    mutate(copy);
    assert.throws(() => parseSession(JSON.stringify(copy)));
  }
});
test('extra targets require valid unique IDs and enforce local capacity', () => {
  let session = makeSession(40);
  assert.throws(() => insertExtra(session, 'missing'));
  assert.throws(() => insertExtra(session, 'horizontal-0', 'horizontal-0'));
  for (let n = session.targets.length; n < 300; n++) session = insertExtra(session, 'horizontal-0', `extra-${n}`);
  assert.throws(() => insertExtra(session, 'horizontal-0', 'extra-last'), /300/);
});
