// Khronos glTF-Validator 실행 (오류 코드별 집계). 사용: npm i gltf-validator && node khronos_validate.mjs <gltf파일> [<gltf파일> ...]
// 같은 폴더의 texture_atlas.webp를 외부 리소스로 제공한다.
import fs from 'fs';
import path from 'path';
import validator from 'gltf-validator';
for (const f of process.argv.slice(2)) {
  const bytes = new Uint8Array(fs.readFileSync(f));
  const dir = path.dirname(path.resolve(f));
  const r = await validator.validateBytes(bytes, {
    maxIssues: 0,
    externalResourceFunction: async (uri) => new Uint8Array(fs.readFileSync(path.join(dir, uri))),
  });
  const c = {};
  for (const m of r.issues.messages) if (m.severity === 0) c[m.code] = (c[m.code] || 0) + 1;
  console.log(path.basename(f).padEnd(24), 'errors=' + r.issues.numErrors, 'warnings=' + r.issues.numWarnings, JSON.stringify(c));
}
