// Local preview only. Serve this viewer subtree, never the repository or photos.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { dirname, extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.PORT || 4173);
const types = { '.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript', '.js': 'text/javascript',
  '.css': 'text/css', '.json': 'application/json', '.jpg': 'image/jpeg' };
const server = createServer(async (request, response) => {
  try {
    if (request.method !== 'GET' && request.method !== 'HEAD') { response.writeHead(405).end(); return; }
    const name = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    const parts = name.split('/').filter(Boolean);
    const allowed = name === '/' || ['index.html', 'app.mjs', 'metadata.mjs', 'viewer.css'].includes(name.slice(1)) ||
      (['fixtures', 'vendor'].includes(parts[0]) && parts.length === 2 && /^[\w-][\w.-]*$/.test(parts[1]));
    const file = resolve(root, name === '/' ? 'index.html' : name.slice(1));
    if (!allowed || !file.startsWith(root + sep)) { response.writeHead(404).end('Not found'); return; }
    const body = await readFile(file);
    response.writeHead(200, { 'Content-Type': types[extname(file)] || 'text/plain', 'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' });
    response.end(request.method === 'HEAD' ? undefined : body);
  } catch { response.writeHead(404).end('Not found'); }
});
server.listen(port, '127.0.0.1', () => console.log(`Local viewer: http://127.0.0.1:${port}/`));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close());
