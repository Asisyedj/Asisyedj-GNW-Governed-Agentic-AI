import fs from 'node:fs';
import crypto from 'node:crypto';
const root = new URL('..', import.meta.url).pathname;
const pkg = JSON.parse(fs.readFileSync(`${root}/package.json`, 'utf8'));
const lock = JSON.parse(fs.readFileSync(`${root}/package-lock.json`, 'utf8'));
const components = Object.entries(lock.packages || {}).filter(([k]) => k && k !== '').map(([path, meta]) => ({
  type: 'library', name: path.replace(/^node_modules\//, ''), version: meta.version || 'unknown', scope: path.includes('node_modules/') ? 'required' : 'root'
}));
const files = ['package.json','package-lock.json'];
const hashes = Object.fromEntries(files.map(f => [f, crypto.createHash('sha256').update(fs.readFileSync(`${root}/${f}`)).digest('hex')]));
const sbom = { bomFormat:'CycloneDX', specVersion:'1.5', version:1, metadata:{component:{type:'application',name:pkg.name,version:pkg.version}, properties:[{name:'evidence_status',value:'LOCAL_MANIFEST_ONLY'}]}, components, hashes, limitations:['No trusted CI signature included.','Dependency installation and vulnerability audit were not executed in this sandbox.'] };
fs.writeFileSync(`${root}/evidence/local/phase15-sbom-local.json`, JSON.stringify(sbom, null, 2)+'\n');
console.log(`WROTE ${root}/evidence/local/phase15-sbom-local.json components=${components.length}`);
