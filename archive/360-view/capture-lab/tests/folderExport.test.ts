import { test } from 'node:test';
import assert from 'node:assert/strict';
import { saveExportToFolder, type ExportReader, type ExportFolder } from '../src/folderExport';

function fixture(options: { size?: number; sourceFailure?: boolean; createFailure?: boolean; writeFailure?: boolean;
  openWriteFailure?: boolean; readBackFailure?: boolean; damage?: 'truncate' | 'corrupt' | 'append' } = {}) {
  const original = Uint8Array.from({ length: 700_000 }, (_, i) => i % 251);
  const events: string[] = [], chunks: Uint8Array[] = [];
  let destination = new Uint8Array();
  function reader(bytes: Uint8Array, label: string): ExportReader {
    let position = 0;
    return {
      async readBytes(length) {
        assert.ok(length <= 256 * 1024);
        if ((label === 'source' && options.sourceFailure) || (label === 'verify' && options.readBackFailure)) throw new Error('Read denied');
        const chunk = bytes.slice(position, position + length); position += chunk.length; return chunk;
      },
      close() { events.push(`${label} closed`); },
    };
  }
  const folder: ExportFolder = {
    createZip(name) {
      events.push(`created ${name}`);
      if (options.createFailure) throw new Error('Folder permission denied');
      return {
        openWrite() {
          if (options.openWriteFailure) throw new Error('Cannot open destination');
          return {
            async writeBytes(bytes) { if (options.writeFailure) throw new Error('Disk full'); chunks.push(bytes.slice()); },
            close() {
              destination = Uint8Array.from(Buffer.concat(chunks));
              if (options.damage === 'truncate') destination = destination.slice(0, -1);
              if (options.damage === 'corrupt') destination[0] = 255;
              if (options.damage === 'append') destination = Uint8Array.from([...destination, 99]);
              events.push('destination closed');
            },
          };
        },
        openRead() { assert.ok(events.includes('destination closed')); return reader(destination, 'verify'); },
      };
    },
  };
  return { original, events, chunks, destination: () => destination, folder,
    source: { size: options.size ?? original.length, openRead: () => reader(original, 'source') } };
}
test('folder provider creates the ZIP and the saved bytes are verified without constructing child paths', async () => {
  const f = fixture(); const progress: string[] = [];
  await saveExportToFolder(f.source, f.folder, 'capture-test.zip', text => progress.push(text));
  assert.deepEqual(f.destination(), f.original);
  assert.equal(f.chunks.length, 3);
  assert.deepEqual(f.events, ['created capture-test.zip', 'destination closed', 'source closed', 'verify closed']);
  assert.ok(progress.includes('Verifying the saved ZIP…'));
});
test('folder permission failure closes the source and provides a sharing fallback', async () => {
  const f = fixture({ createFailure: true });
  await assert.rejects(saveExportToFolder(f.source, f.folder, 'test.zip'), /originals.*kept.*Share original capture ZIP.*permission denied/);
  assert.ok(f.events.includes('source closed'));
});
test('destination open failure closes the source', async () => {
  const f = fixture({ openWriteFailure: true });
  await assert.rejects(saveExportToFolder(f.source, f.folder, 'test.zip'), /Cannot open destination/);
  assert.ok(f.events.includes('source closed'));
});
test('disk-full failure closes both descriptors and never reports a saved copy', async () => {
  const f = fixture({ writeFailure: true });
  await assert.rejects(saveExportToFolder(f.source, f.folder, 'test.zip'), /Disk full/);
  assert.ok(f.events.includes('destination closed') && f.events.includes('source closed'));
});
test('source read failure closes both descriptors', async () => {
  const f = fixture({ sourceFailure: true });
  await assert.rejects(saveExportToFolder(f.source, f.folder, 'test.zip'), /Read denied/);
  assert.ok(f.events.includes('destination closed') && f.events.includes('source closed'));
});
test('short source read fails before saved-copy verification', async () => {
  const f = fixture({ size: 800_000 });
  await assert.rejects(saveExportToFolder(f.source, f.folder, 'test.zip'), /read was incomplete/);
  assert.ok(!f.events.includes('verify closed'));
});
test('saved copy truncation is detected', async () => {
  const f = fixture({ damage: 'truncate' });
  await assert.rejects(saveExportToFolder(f.source, f.folder, 'test.zip'), /verification failed/);
  assert.ok(f.events.includes('verify closed'));
});
test('saved copy corruption with unchanged length is detected', async () => {
  const f = fixture({ damage: 'corrupt' });
  await assert.rejects(saveExportToFolder(f.source, f.folder, 'test.zip'), /verification failed/);
});
test('unexpected bytes after the ZIP are detected', async () => {
  const f = fixture({ damage: 'append' });
  await assert.rejects(saveExportToFolder(f.source, f.folder, 'test.zip'), /extra bytes/);
});
test('readback permission failure is not reported as successful delivery', async () => {
  const f = fixture({ readBackFailure: true });
  await assert.rejects(saveExportToFolder(f.source, f.folder, 'test.zip'), /Read denied/);
  assert.ok(f.events.includes('verify closed'));
});
test('unsafe filenames fail before creating any destination', async () => {
  const f = fixture();
  await assert.rejects(saveExportToFolder(f.source, f.folder, '../test.zip'), /Invalid export/);
  assert.deepEqual(f.events, []);
});
