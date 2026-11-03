// Reproducible Pannellum 2.5.7 bundle with one local renderer correction.
// NPOT equirectangular textures use CLAMP_TO_EDGE in upstream WebGL1. That
// suppresses interpolation between the last and first columns, producing a
// magnified line at longitude +/-180. Interpolate those existing pixels
// periodically in the shader; do not modify images, angles, or input hashes.
import { readFile, writeFile, mkdir, copyFile } from 'node:fs/promises';
const packageRoot = new URL('./node_modules/pannellum/', import.meta.url);
const output = new URL('./vendor/', import.meta.url);
const pkg = JSON.parse(await readFile(new URL('package.json', packageRoot)));
if (pkg.version !== '2.5.7') throw new Error('Review the periodic-sampling patch before changing Pannellum versions.');
let renderer = await readFile(new URL('src/js/libpannellum.js', packageRoot), 'utf8');
function replaceOne(before, after) {
  if (renderer.split(before).length !== 2) throw new Error('Unexpected upstream source; periodic patch not applied.');
  renderer = renderer.replace(before, after);
}
replaceOne("gl.uniform1f(program.h, haov / (Math.PI * 2.0));",
  "gl.uniform1f(program.h, haov / (Math.PI * 2.0));\n            gl.uniform1f(gl.getUniformLocation(program, 'u_imageWidth'), image.width || 1);");
replaceOne("'uniform bool u_splitImage;',", "'uniform bool u_splitImage;',\n'uniform float u_imageWidth;',");
replaceOne("'uniform vec4 u_backgroundColor;',", `'uniform vec4 u_backgroundColor;',
// Local correction: sample either half at the original horizontal pixel center.
'vec4 sampleLongitude(vec2 uv) {',
    'if (u_splitImage) {',
        'if (uv.x < 0.5) return texture2D(u_image0, vec2(uv.x * 2.0, uv.y));',
        'return texture2D(u_image1, vec2(uv.x * 2.0 - 1.0, uv.y));',
    '}',
    'return texture2D(u_image0, uv);',
'}',`);
replaceOne("'if(u_splitImage) {',", `'if(u_h > 0.999999) {',
    'vec2 uv = vec2((coord.x + u_h) / (u_h * 2.0), (-coord.y + u_v + u_vo) / (u_v * 2.0));',
    'float px = uv.x * u_imageWidth - 0.5;',
    'float left = floor(px);',
    'vec4 a = sampleLongitude(vec2((mod(left, u_imageWidth) + 0.5) / u_imageWidth, uv.y));',
    'vec4 b = sampleLongitude(vec2((mod(left + 1.0, u_imageWidth) + 0.5) / u_imageWidth, uv.y));',
    'gl_FragColor = mix(a, b, fract(px));',
'} else if(u_splitImage) {',`);
const viewer = await readFile(new URL('src/js/pannellum.js', packageRoot), 'utf8');
await mkdir(output, { recursive: true });
await writeFile(new URL('pannellum.js', output), '// Pannellum 2.5.7 + local periodic interpolation fix; see build-vendor.mjs.\n' + renderer + '\n' + viewer);
await copyFile(new URL('build/pannellum.css', packageRoot), new URL('pannellum.css', output));
await copyFile(new URL('COPYING', packageRoot), new URL('COPYING', output));
console.log('Built local Pannellum 2.5.7 bundle with periodic horizontal sampling.');
