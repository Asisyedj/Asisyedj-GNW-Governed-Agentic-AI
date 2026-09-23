import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve('src/server');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const checks = [
  { file: 'llm.ts', sink: 'llm.chat POST', required: ['executeFencedExternal', 'idempotency-key', 'x-gnw-fence-token'] },
  { file: 'notify.ts', sink: 'notification webhook POST', required: ['executeFencedExternal', 'idempotency-key', 'x-gnw-fence-token'] },
  { file: 'video.ts', sink: 'video provider POST', required: ['executeFencedExternal', 'idempotency-key', 'x-gnw-fence-token'] },
  { file: 'video.ts', sink: 'artifact storage from video completion', required: ['executeFencedExternal', 'GNW-ARTIFACT-IDEMPOTENCY-V1'] },
  { file: 'app.ts', sink: 'artifact storage upload', required: ['executeFencedExternal', 'GNW-ARTIFACT-IDEMPOTENCY-V1'] },
];
const results = checks.map(check => {
  const source = read(check.file);
  const missing = check.required.filter(token => !source.includes(token));
  return { ...check, status: missing.length ? 'FAIL' : 'PASS', missing };
});
const localGuarded = [
  ['tools/executor.ts', 'local/remote command and file operations', 'GUARDED_LOCAL_EFFECT; remote provider contract separately required'],
  ['tools/git.ts', 'sandbox git commit and PR simulation', 'GUARDED_LOCAL_EFFECT; provider integration separately required'],
  ['tools/memory.ts', 'in-process memory store', 'LOCAL_STATE; no network provider'],
  ['tools/code-intel.ts', 'sandbox code inspection', 'READ_ONLY_LOCAL'],
  ['tools/browser.ts', 'browser GET', 'READ_ONLY_SSRF_GUARDED'],
  ['tools/visual-browser.ts', 'browser GET and synthetic action', 'READ_ONLY_OR_SYNTHETIC; no real browser mutation'],
].map(([file, sink, status]) => ({ file, sink, status }));
const report = { schema: 'GNW.ExternalSinkValidation.v1', status: results.every(item => item.status === 'PASS') ? 'PASS_STATIC_CONTRACTS' : 'FAIL', requiredFencedSinks: results, reviewedNonNetworkPaths: localGuarded, providerContractProof: 'REQUIRES_REAL_PROVIDER_EVIDENCE' };
console.log(JSON.stringify(report, null, 2));
if (report.status !== 'PASS_STATIC_CONTRACTS') process.exit(1);
