from pathlib import Path

path = Path('/home/ubuntu/gnw-phase5-implementation-2026-09-15/gnw/docs/security/100-independent-review-evidence.yaml')
text = path.read_text()
timestamp = '2026-09-15T09:49:25Z'
evidence = '/home/ubuntu/gnw-phase5-evidence-batch1-vitest.log'
updates = {
    'IRS-031': {
        'attack': 'Flip signed grant material after Ed25519 signing',
        'precondition': 'security-v3.test.ts grant signing and verification fixture',
        'actual': 'Tampered normalizedParameters signature verification returned false',
        'audit_evidence': f'{evidence}; tests/security-v3.test.ts:17-23',
        'root_cause': 'Signature binds canonical grant material',
        'fix': 'Ed25519 grant signature verification',
    },
    'IRS-038': {
        'attack': 'Substitute actor or tenant in capability execution envelope',
        'precondition': 'phase3-security-boundaries.test.ts capability binding fixture',
        'actual': 'Central execution gate rejected capability_binding and remote executor rejected executor_authorization_binding; effect did not run',
        'audit_evidence': f'{evidence}; tests/phase3-security-boundaries.test.ts:85-145',
        'root_cause': 'Capability lease is bound to actor, tenant, task, action and capability',
        'fix': 'Executor-independent binding enforcement',
    },
    'IRS-040': {
        'attack': 'Activate kill switch after lease admission and replay stale lease',
        'precondition': 'phase3-security-boundaries.test.ts durable interlock fixture',
        'actual': 'Interlock generation advanced from 0 to 2; stale lease was rejected with stale_interlock_generation; effect count remained zero',
        'audit_evidence': f'{evidence}; tests/phase3-security-boundaries.test.ts:48-82',
        'root_cause': 'Final interlock generation check fences stale authority immediately before effect',
        'fix': 'Durable generation-based final interlock',
    },
    'IRS-061': {
        'attack': 'Request an unapproved external destination',
        'precondition': 'egress-interlock.test.ts allowlist fixture',
        'actual': 'Unapproved destination was rejected with egress_destination_not_allowlisted',
        'audit_evidence': f'{evidence}; tests/egress-interlock.test.ts:10-16',
        'root_cause': 'External destinations require explicit allowlisting',
        'fix': 'Default-deny egress allowlist',
    },
    'IRS-062': {
        'attack': 'Use plain HTTP or URL credentials for an external sink',
        'precondition': 'egress-interlock.test.ts HTTPS fixture',
        'actual': 'HTTP was rejected with https_required and URL credentials with url_credentials_forbidden',
        'audit_evidence': f'{evidence}; tests/egress-interlock.test.ts:5-8',
        'root_cause': 'External sink URLs require HTTPS and cannot contain credentials',
        'fix': 'HTTPS and URL-credential validation',
    },
    'IRS-063': {
        'attack': 'Target localhost, loopback or RFC1918 private address',
        'precondition': 'egress-interlock.test.ts private destination fixture',
        'actual': 'localhost, 127.0.0.1 and 10.0.0.1 were rejected with private_destination_blocked',
        'audit_evidence': f'{evidence}; tests/egress-interlock.test.ts:10-14',
        'root_cause': 'Private and local destinations are denied before egress',
        'fix': 'Private/local destination blocking',
    },
    'IRS-064': {
        'attack': 'Target cloud metadata IP or metadata hostname',
        'precondition': 'egress-interlock.test.ts metadata destination fixture',
        'actual': '169.254.169.254 and metadata.google.internal were rejected with private_destination_blocked',
        'audit_evidence': f'{evidence}; tests/egress-interlock.test.ts:10-14',
        'root_cause': 'Metadata destinations are treated as private/local and denied',
        'fix': 'Cloud metadata endpoint blocking',
    },
}

for subject_id, values in updates.items():
    marker = f'  - subject_id: {subject_id}\n'
    start = text.index(marker)
    next_marker = text.find('  - subject_id: ', start + len(marker))
    end = next_marker if next_marker != -1 else len(text)
    block = text[start:end]
    replacements = {
        '    attack:': f'    attack: "{values["attack"]}"',
        '    precondition:': f'    precondition: "{values["precondition"]}"',
        '    actual:': f'    actual: "{values["actual"]}"',
        '    audit_evidence:': f'    audit_evidence: "{values["audit_evidence"]}"',
        '    verdict:': '    verdict: PASS',
        '    root_cause:': f'    root_cause: "{values["root_cause"]}"',
        '    fix:': f'    fix: "{values["fix"]}"',
        '    regression:': '    regression: PASS',
        '    reviewer:': '    reviewer: "Automated local Phase 5 evidence runner"',
        '    review_timestamp:': f'    review_timestamp: "{timestamp}"',
    }
    for prefix, replacement in replacements.items():
        lines = block.splitlines()
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                lines[i] = replacement
                break
        block = '\n'.join(lines) + ('\n' if block.endswith('\n') else '')
    text = text[:start] + block + text[end:]

text = text.replace('status: INCOMPLETE', 'status: PARTIAL_VERIFIED_BATCH_1')
path.write_text(text)
print(f'updated={len(updates)}')
