import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
// Load this standalone browser ES module without introducing a package manifest.
const source = readFileSync(new URL('../web/highlight.js', import.meta.url), 'utf8');
const {segments} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
const text = '🏠 Clean <script>alert(1)</script> clean';
const parts = segments(text, [{start: 2, end: 7}, {start: 33, end: 38}]);
assert.equal(parts.map(p => p.text).join(''), text);
assert.equal(parts[1].text, 'Clean');
assert.equal(parts[1].marked, true);
for (const malformed of [undefined, null, {}, [null, {start:-1,end:3}, {start:2,end:999}, {start:'2',end:7}]]) {
  assert.deepEqual(segments(text, malformed), [{text, marked:false}]);
}
assert.equal(segments('parking parking', [{start:0,end:7}, {start:0,end:7}, {start:8,end:15}]).filter(p => p.marked).length, 2);
assert.equal(segments('water pressure', [{start:0,end:14}])[0].text, 'water pressure');
console.log('Highlight checks passed: Unicode, preservation, malformed spans, duplicate spans, phrases.');
