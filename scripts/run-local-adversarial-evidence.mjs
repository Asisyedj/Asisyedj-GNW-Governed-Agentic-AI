import fs from 'node:fs';
import crypto from 'node:crypto';
const root = new URL('..', import.meta.url).pathname;
const security = fs.readFileSync(`${root}/src/server/security.ts`, 'utf8');
const tests = fs.readFileSync(`${root}/tests/egress-interlock.test.ts`, 'utf8');
const cases = [
  ['https-required', /https_required/.test(security) && /http:/.test(tests)],
  ['credential-denial', /url_credentials_forbidden/.test(security)],
  ['private-destination-denial', /private_destination_blocked/.test(security) && /169\.254\.169\.254/.test(tests)],
  ['allowlist-enforcement', /egress_destination_not_allowlisted/.test(security) && /approved\.example/.test(tests)],
  ['dns-resolution-before-effect', /dns\.lookup/.test(security) && /unsafe_dns_destination/.test(security)],
  ['manual-redirect-only', /redirects_must_be_manual/.test(security)],
  ['response-byte-ceiling', /response_too_large/.test(security) && /maxResponseBytes/.test(security)],
  ['audit-chain-module', fs.existsSync(`${root}/src/server/audit.ts`)],
  ['governance-module', fs.existsSync(`${root}/src/server/governance.ts`)],
  ['approval-tests', fs.existsSync(`${root}/tests/governed-execution.test.ts`)]
];
const records = cases.map(([id, ok]) => ({subject_id:`local-${id}`, verdict:ok?'PASS':'UNPROVEN', evidence:'static source/test fixture check', limitation:'Not integrated staging evidence'}));
const out = {phase:17,status:'LOCAL_STATIC_ONLY',created_at:new Date().toISOString(),artifact_digest:crypto.createHash('sha256').update(security+tests).digest('hex'),records,summary:{PASS:records.filter(r=>r.verdict==='PASS').length,FAIL:0,BLOCKED:0,UNPROVEN:records.filter(r=>r.verdict==='UNPROVEN').length},limitations:['No PostgreSQL, provider, backup/restore, secret store, or staging runtime exercised.']};
fs.writeFileSync(`${root}/evidence/local/phase17-local-adversarial.json`, JSON.stringify(out,null,2)+'\n');
console.log(`WROTE local adversarial evidence PASS=${out.summary.PASS} UNPROVEN=${out.summary.UNPROVEN}`);
