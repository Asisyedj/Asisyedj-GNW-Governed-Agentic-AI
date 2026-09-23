import fs from 'node:fs';
import path from 'node:path';

const file = path.resolve('release/RELEASE-EVIDENCE.json');
const evidence = JSON.parse(fs.readFileSync(file, 'utf8'));
const requiredGates = [
  'local_clean_install', 'local_typecheck', 'local_tests', 'local_build', 'dependency_audit',
  'container_build', 'tls_postgres_multi_instance', 'ssrf_dns_rebinding',
  'distributed_kill_switch', 'backup_restore_anti_resurrection', 'secret_rotation',
  'supply_chain_signing', 'irs_100_evidence', 'independent_review', 'accredited_certification',
];
const failures = [];
for (const gate of requiredGates) {
  if (evidence.gates?.[gate] !== 'PASS') failures.push(`${gate}=${evidence.gates?.[gate] ?? 'MISSING'}`);
}
if (evidence.status !== 'PASS') failures.push(`status=${evidence.status ?? 'MISSING'}`);
if (!evidence.review?.reviewer || evidence.review.reviewer === 'UNASSIGNED') failures.push('reviewer=UNASSIGNED');
if (!evidence.review?.organization || evidence.review.organization === 'UNASSIGNED') failures.push('organization=UNASSIGNED');
if (!evidence.review?.timestamp || Number.isNaN(Date.parse(evidence.review.timestamp))) failures.push('review_timestamp=MISSING_OR_INVALID');
if (!evidence.review?.signature || evidence.review.signature === 'MISSING') failures.push('signature=MISSING');

if (failures.length) {
  console.error('RELEASE BLOCKED: required release evidence is incomplete.');
  for (const failure of failures) console.error(` - ${failure}`);
  process.exit(2);
}
console.log('PASS: release evidence is complete and independently attested.');
