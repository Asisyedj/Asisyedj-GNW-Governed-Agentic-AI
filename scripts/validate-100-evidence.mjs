import fs from 'node:fs';
import path from 'node:path';

const file = path.resolve('docs/security/100-independent-review-evidence.yaml');
const text = fs.readFileSync(file, 'utf8');
const expected = Array.from({ length: 100 }, (_, i) => `IRS-${String(i + 1).padStart(3, '0')}`);
const starts = [...text.matchAll(/^\s+- subject_id: (IRS-\d{3})$/gm)];

if (starts.length !== 100) throw new Error(`FAIL: expected 100 evidence records, found ${starts.length}`);
const ids = starts.map(match => match[1]);
if (new Set(ids).size !== 100) throw new Error('FAIL: duplicate evidence subject IDs');
for (let i = 0; i < expected.length; i += 1) {
  if (ids[i] !== expected[i]) throw new Error(`FAIL: missing/out-of-order ${expected[i]}`);
}

const requiredFields = [
  'attack', 'precondition', 'expected', 'actual', 'side_effect', 'audit_evidence',
  'verdict', 'root_cause', 'fix', 'regression', 'reviewer', 'review_timestamp',
];
const records = starts.map((match, index) => {
  const start = match.index;
  const end = index + 1 < starts.length ? starts[index + 1].index : text.length;
  const block = text.slice(start, end);
  const record = { subject_id: match[1] };
  for (const field of requiredFields) {
    const found = block.match(new RegExp(`^\\s+${field}:\\s*(.*)$`, 'm'));
    if (!found) throw new Error(`FAIL: ${match[1]} missing field ${field}`);
    record[field] = found[1].trim().replace(/^"|"$/g, '');
  }
  return record;
});

const validVerdicts = new Set(['PASS', 'FAIL', 'BLOCKED', 'UNPROVEN']);
const placeholders = new Set(['', 'MISSING', 'NOT_EXECUTED', 'UNASSIGNED', 'UNPROVEN', 'SEE_MATRIX']);
const counts = { PASS: 0, FAIL: 0, BLOCKED: 0, UNPROVEN: 0 };
const evidenceErrors = [];
for (const record of records) {
  if (!validVerdicts.has(record.verdict)) throw new Error(`FAIL: ${record.subject_id} invalid verdict ${record.verdict}`);
  counts[record.verdict] += 1;
  if (record.verdict === 'PASS') {
    for (const field of ['attack', 'precondition', 'actual', 'audit_evidence', 'regression', 'reviewer', 'review_timestamp']) {
      if (placeholders.has(record[field])) evidenceErrors.push(`${record.subject_id}: PASS has placeholder ${field}`);
    }
    if (record.regression !== 'PASS') evidenceErrors.push(`${record.subject_id}: PASS requires regression: PASS`);
    if (Number.isNaN(Date.parse(record.review_timestamp))) evidenceErrors.push(`${record.subject_id}: invalid review_timestamp`);
  }
}

console.log('PASS: 100 evidence records structurally present');
console.log(`VERDICTS: PASS=${counts.PASS} FAIL=${counts.FAIL} BLOCKED=${counts.BLOCKED} UNPROVEN=${counts.UNPROVEN}`);

if (evidenceErrors.length) {
  for (const error of evidenceErrors.slice(0, 25)) console.error(`EVIDENCE ERROR: ${error}`);
  if (evidenceErrors.length > 25) console.error(`EVIDENCE ERROR: ${evidenceErrors.length - 25} additional errors omitted`);
}
if (counts.FAIL > 0 || counts.BLOCKED > 0 || counts.UNPROVEN > 0 || counts.PASS !== 100 || evidenceErrors.length > 0) {
  console.error('RELEASE BLOCKED: all 100 subjects require evidence-complete PASS records.');
  process.exitCode = 2;
}
