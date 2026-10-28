# Continuous Audit Report

## Pytest results for perplexity-browser-api
Exit code: 0
```
......................ss................................................ [ 67%]
...................................                                      [100%]
============================== warnings summary ===============================
personal_agent\tests\test_mission_proof.py:214
  D:\GNW\perplexity-browser-api\personal_agent\tests\test_mission_proof.py:214: PytestUnknownMarkWarning: Unknown pytest.mark.integration - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.integration

personal_agent\tests\test_mission_proof.py:220
  D:\GNW\perplexity-browser-api\personal_agent\tests\test_mission_proof.py:220: PytestUnknownMarkWarning: Unknown pytest.mark.integration - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.integration

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
105 passed, 2 skipped, 2 warnings in 8.76s

```

## Evidence verification for perplexity-browser-api
Exit code: 0
```
============================================================
GNW Evidence Verification
============================================================

[1/4] Checking evidence file existence...
  [PASS] OK: evidence/unit_tests.xml
  [PASS] OK: evidence/security_tests.xml

[2/4] Validating JUnit XML evidence...
  [PASS] evidence/unit_tests.xml: 9 tests, 0 failures, 0 errors
  [PASS] evidence/security_tests.xml: 48 tests, 0 failures, 0 errors

[3/4] Skipping security scan evidence (not required in this mode)

[4/4] Computing evidence hashes for audit trail...
  evidence/unit_tests.xml: sha256:28486c2f58e0d32d9ab66a7dbfb611ede579d9ba8e40dd5d6259d6e0f585741d
  evidence/security_tests.xml: sha256:1fc2aa8cd9e7ebeafc72f0c5293b33024b98fcc0d161693744056f2bf2cd2756

============================================================
ALL EVIDENCE GATES PASSED
============================================================

```