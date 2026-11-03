/** Desktop interoperability check of the exact mobile ZIP writer; no native mocks required. */
import { createReadStream } from 'node:fs';
import { open, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { parseSession } from '../src/domain';
import { writeSessionZip } from '../src/exportSession';

async function main() {
  const [input, output] = process.argv.slice(2);
  if (!input || !output) throw new Error('Usage: npx tsx tools/export-fixture.ts INPUT_FOLDER OUTPUT.zip');
  const manifest = JSON.parse(await readFile(path.join(input, 'manifest.json'), 'utf8'));
  const session = parseSession(JSON.stringify(manifest.session));
  const paths = new Map<string, { uri: string; width: number; height: number }>(manifest.photos.map((p: { filename: string; path: string; width: number; height: number }) =>
    [p.filename, { uri: path.join(input, p.path), width: p.width, height: p.height }]));
  const file = await open(output, 'wx');
  try {
    await writeSessionZip(session, {
      async inspect(uri) {
        const photo = [...paths.values()].find(p => p.uri === uri)!;
        return { bytes: (await stat(uri)).size, width: photo.width, height: photo.height };
      },
      async *chunks(uri) { for await (const chunk of createReadStream(uri, { highWaterMark: 256 * 1024 })) yield chunk; },
    }, filename => paths.get(filename)!.uri, async bytes => {
      let offset = 0;
      while (offset < bytes.length) {
        const { bytesWritten } = await file.write(bytes, offset, bytes.length - offset);
        if (!bytesWritten) throw new Error('Short output write');
        offset += bytesWritten;
      }
    }, 3 * 1024 ** 3);
  } finally { await file.close(); }
  console.log(`Exported unchanged fixture originals to ${output}`);
}
void main().catch(error => { console.error(error); process.exitCode = 1; });
