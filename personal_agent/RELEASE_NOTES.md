# Release Notes

## Unreleased — 2026-10-25

### Added
- Added deterministic tests for default LLM routing when `model_name` is omitted.
- Added a mocked routing test confirming that `model_name="perplexity/sonar-2"` is passed to `call_llm_with_model`.
- Verified that a proposed PowerShell action remains blocked when no approval callback is supplied.

### Verified
- New model-routing tests: **2 passed**.
- Full `personal_agent` test suite: **13 passed**.
- Python compile check for agent, plugins, safety, and tests: **passed**.
- Registry resolves `powershell` to `personal_agent.plugins.powershell_tool.PowerShellTool`.
- Staged whitespace check: **passed**.

### Scope and limitations
- Model routing was tested with mocks; no live model inference was performed.
- No PowerShell tool implementation was deleted or modified in this change.
- The release is not tagged or committed yet; Git commit author identity must be configured before committing.
