export function localPath(path: string): string {
  if (path !== '' && !/^[a-z0-9-]+(?:\/[a-z0-9.-]+)?$/.test(path)) throw new Error('Invalid local capture path.');
  if (path.split('/').some(part => part === '..' || part === '.')) throw new Error('Invalid local capture path.');
  return path;
}

export function isCameraCacheUri(uri: string, cacheRoot: string): boolean {
  const candidate = fileUriSegments(uri);
  const root = fileUriSegments(cacheRoot);
  if (!candidate || !root || root.length === 0 || candidate.length <= root.length) return false;
  if (!root.every((part, index) => part === candidate[index])) return false;
  // Expo Go's trusted root can contain literal percent-encoded project IDs.
  // Camera-generated child names need no second layer of URI decoding.
  return candidate.slice(root.length).every(part => !part.includes('%'));
}

function fileUriSegments(uri: string): string[] | null {
  // Accept local file:/ and file:/// URIs, never a host, query or fragment.
  // Do not use URL normalization here: it can erase traversal before validation.
  if (/[\\\u0000-\u001f\u007f]/.test(uri)) return null;
  const match = /^file:(?:\/\/)?(\/[^?#]*)$/i.exec(uri);
  if (!match) return null;
  const parts = match[1]!.slice(1).split('/');
  if (parts.at(-1) === '') parts.pop();
  try {
    const decoded = parts.map(part => decodeURIComponent(part));
    if (decoded.some(part => part === '' || part === '.' || part === '..' || /[\/\\\u0000-\u001f\u007f]/.test(part))) return null;
    // Decode once: %252F in a project name denotes literal %2F, not a slash.
    return decoded;
  } catch { return null; }
}
