import type { Env } from "../env.js";
import { executeInRemoteExecutor, type RemoteExecutionResult } from "../executor-client.js";
import { TaskSandbox, type SandboxOptions, type SandboxRunResult } from "./index.js";

export type SandboxJob = {
  taskId: number;
  command: string;
  args?: string[];
  files?: Array<{ path: string; content: string }>;
  timeoutMs?: number;
  maxOutputBytes?: number;
};

export interface SandboxAdapter {
  readonly mode: "local-test" | "remote-managed";
  execute(job: SandboxJob, options?: SandboxOptions): Promise<SandboxRunResult>;
}

export class LocalSandboxAdapter implements SandboxAdapter {
  readonly mode = "local-test" as const;
  constructor(private readonly baseDir: string) {}

  async execute(job: SandboxJob, options: SandboxOptions = {}) {
    const sandbox = new TaskSandbox(job.taskId, this.baseDir);
    await sandbox.init();
    for (const file of job.files ?? []) await sandbox.writeFile(file.path, file.content);
    return sandbox.execute(job.command, job.args ?? [], { ...options, timeoutMs: job.timeoutMs, maxOutputBytes: job.maxOutputBytes });
  }
}

export class RemoteSandboxAdapter implements SandboxAdapter {
  readonly mode = "remote-managed" as const;
  constructor(private readonly env: Env) {}

  async execute(job: SandboxJob): Promise<RemoteExecutionResult> {
    if (!this.env.executorRequired) throw new Error("remote_executor_not_required");
    return executeInRemoteExecutor(this.env, job);
  }
}

/** Production must select a separately deployed executor; local execution is test/development only. */
export function createSandboxAdapter(env: Env): SandboxAdapter {
  return env.executorRequired ? new RemoteSandboxAdapter(env) : new LocalSandboxAdapter(`${env.artifactDir}/sandboxes`);
}
