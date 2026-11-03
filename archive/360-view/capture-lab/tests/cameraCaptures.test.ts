import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CameraCaptures, CAPTURE_BUILD, cameraFileError } from '../src/cameraCaptures';
import { isCameraCacheUri } from '../src/localPaths';

test('a fresh native capture can be copied when camera and filesystem cache roots differ', () => {
  const captures = new CameraCaptures();
  const uri = 'file:///data/user/0/host.exp.exponent/cache/Camera/photo.jpg';
  const root = 'file:///data/user/0/host.exp.exponent/cache/ExperienceData/%2540anonymous%252Flab/';
  assert.equal(isCameraCacheUri(uri, root), false);
  assert.throws(() => captures.require(uri), /current camera capture/);
  captures.register(uri);
  assert.doesNotThrow(() => captures.require(uri));
  // Provenance does not relax the separate deletion boundary.
  assert.equal(isCameraCacheUri(uri, root), false);
});

test('native camera registration supports encoded and aliased local file URIs', () => {
  const captures = new CameraCaptures();
  for (const uri of [
    'file:/data/user/0/app/cache/Camera/photo.jpg',
    'file:///data/data/app/cache/Camera/photo.jpg',
    'file:///app/cache/ExperienceData/%2540owner%252Flab/Camera/photo.jpg',
    'file:///app/cache/ExperienceData/%40owner%2Flab/Camera/photo.jpeg',
  ]) {
    captures.register(uri);
    assert.doesNotThrow(() => captures.require(uri));
  }
});

test('restored metadata and a different photo do not acquire camera provenance', () => {
  const captures = new CameraCaptures();
  captures.register('file:///app/cache/Camera/current.jpg');
  assert.throws(() => captures.require('file:///app/cache/Camera/other.jpg'));
  const afterReload = new CameraCaptures();
  assert.throws(() => afterReload.require('file:///app/cache/Camera/current.jpg'));
});

test('camera provenance is removed after a capture attempt', () => {
  const captures = new CameraCaptures();
  const uri = 'file:///app/cache/Camera/photo.jpg';
  captures.register(uri);
  captures.forget(uri);
  assert.throws(() => captures.require(uri));
  assert.doesNotThrow(() => captures.forget(uri));
});

test('registration refuses remote sources, traversal, malformed URIs and non-JPEGs', () => {
  const captures = new CameraCaptures();
  for (const uri of [
    'https://example.com/photo.jpg', 'content://photos/1.jpg',
    'file://other-host/cache/photo.jpg', 'file:////other-host/photo.jpg',
    'file:///cache/../photo.jpg', 'file:///cache/%2e%2e/photo.jpg',
    'file:///cache/%2f..%2fphoto.jpg', 'file:///cache/photo.jpg?file=other',
    'file:///cache/photo.jpg#other', 'file:///cache/%00photo.jpg',
    'file:///cache/%ZZ.jpg', 'file:///cache/photo.png',
  ]) assert.throws(() => captures.register(uri), uri);
});

test('native copy errors expose the build, both paths and the actual native reason', () => {
  const error = cameraFileError('file:///camera/photo.jpg', 'file:///other-cache/', new Error('Permission denied'));
  assert.ok(error.message.includes(CAPTURE_BUILD));
  assert.match(error.message, /Camera file: file:\/\/\/camera\/photo.jpg/);
  assert.match(error.message, /FileSystem cache: file:\/\/\/other-cache\//);
  assert.match(error.message, /Permission denied/);
});
