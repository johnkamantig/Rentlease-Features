// API offsets use Unicode code points, not JavaScript UTF-16 code units.
export function segments(text, spans) {
  const chars = Array.from(typeof text === 'string' ? text : '');
  const valid = (Array.isArray(spans) ? spans : []).filter(s =>
    s && Number.isInteger(s.start) && Number.isInteger(s.end) &&
    s.start >= 0 && s.end > s.start && s.end <= chars.length
  ).sort((a, b) => a.start - b.start || a.end - b.end);
  const result = [];
  let cursor = 0;
  for (const span of valid) {
    if (span.start < cursor) continue;
    if (span.start > cursor) result.push({text: chars.slice(cursor, span.start).join(''), marked: false});
    result.push({text: chars.slice(span.start, span.end).join(''), marked: true});
    cursor = span.end;
  }
  if (cursor < chars.length) result.push({text: chars.slice(cursor).join(''), marked: false});
  return result;
}
