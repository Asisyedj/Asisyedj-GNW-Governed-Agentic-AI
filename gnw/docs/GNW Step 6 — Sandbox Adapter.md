# GNW Step 6 — Sandbox Adapter

**Status:** Step 6 code boundary implemented and verified. A real managed sandbox deployment and hostile-code assessment remain external infrastructure gates.

## Implemented decision

GNW now has a provider-neutral `SandboxAdapter` contract. The local `TaskSandbox` is selected only when remote execution is not required. When `GNW_EXECUTOR_REQUIRED=true`, the adapter selects the remote executor client and refuses to silently fall back to local execution.

The adapter carries task ID, command, arguments, optional files, timeout, and output limit. Remote calls continue through the governed HTTPS/egress client. The remote executor response is validated by the existing Step 4 boundary before it becomes tool output.

## Evidence

| Control | Result |
|---|---|
| Local adapter selection | Unit test pass |
| Remote adapter selection | Unit test pass |
| No silent local fallback | Unit test pass |
| Remote executor required configuration | Existing production readiness check |
| HTTPS and host allowlisting | Existing governed fetch and egress checks |
| Response contract validation | Existing executor-client tests |

## Limitations

The adapter does not claim that a local Node child process is a hostile-code isolation boundary. Production still requires a separately deployed managed executor with a non-root identity, read-only image, explicit workspace mount, CPU/memory/process/time limits, default-deny network policy, no GNW credentials, and a kill path.

The remote executor is not connected in this sandbox because no provider, endpoint credential, region, data-retention contract, or network policy was supplied. Therefore this step is code-complete but not production-certified.

## Required external evidence

1. Select E2B, AgentCore, Modal, Cloudflare Sandbox, or another reviewed provider.
2. Deploy the executor separately from the API process.
3. Prove that executor code cannot read GNW credentials or another tenant workspace.
4. Run command injection, shell escape, traversal, symlink, process-spawn, fork-bomb, network, DNS-rebinding, output-limit, timeout, and workspace-isolation tests.
5. Capture provider version, region, limits, network policy, logs, cleanup result, artifact digest, and independent review.

**Next step:** Step 7 — egress and interlock enforcement. The roadmap's Step 7 Secrets Broker was completed in the previous continuation package; the next unfinished step is the egress/interlock boundary.

## References

[1]: https://e2b.dev/ "E2B isolated agent cloud and microVM runtime"
[2]: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html "Amazon Bedrock AgentCore overview"
