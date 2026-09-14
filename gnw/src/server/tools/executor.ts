import type { Db } from "../db/index.js";
import type { Env } from "../env.js";
import type { SessionUser } from "../auth.js";
import type { CapabilityLease } from "../capability.js";
import { executeExternal, ExecutionDenied } from "../execution.js";
import { TaskSandbox } from "../sandbox/index.js";
import { executeInRemoteExecutor } from "../executor-client.js";
import { analyzeCommandRisk } from "../security/guard.js";
import * as repo from "../repo.js";

export type ExecutionToolResult = {
  success: boolean;
  output?: string;
  error?: string;
  exitCode?: number | null;
  durationMs?: number;
};

/**
 * Governed Command Execution Tool (`exec.command`).
 * Runs sandboxed shell commands admitted by cryptographic capability lease.
 */
export async function runGovernedCommand(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  command: string;
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<ExecutionToolResult> {
  const analysis = analyzeCommandRisk(p.command);
  if (analysis.requiresHumanApproval) {
    throw new ExecutionDenied("destructive_command_requires_human_approval");
  }

  const sandbox = new TaskSandbox(p.taskId, p.env.artifactDir ? `${p.env.artifactDir}/sandboxes` : "./data/sandboxes");
  const checkInterlock = async () => {
    const interlock = await repo.getInterlock(p.db);
    return interlock.killSwitch || interlock.circuitOpen;
  };

  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "sandboxed_command_execution",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "exec.command",
    effect: async () => {
      const result = p.env.executorRequired
        ? await executeInRemoteExecutor(p.env, { taskId: p.taskId, command: p.command, timeoutMs: 45_000, maxOutputBytes: p.env.maxBudgetBytes })
        : await sandbox.execute(p.command, [], {
            checkInterlock,
            timeoutMs: 45_000,
            maxOutputBytes: p.env.maxBudgetBytes,
          });

      if (result.timedOut) {
        return { success: false, error: "execution_timed_out", exitCode: result.exitCode };
      }

      const output = [
        result.stdout.trim(),
        result.stderr.trim() ? `[stderr]\n${result.stderr.trim()}` : "",
      ].filter(Boolean).join("\n\n");

      return {
        success: result.exitCode === 0,
        output: output || "(command executed with empty output)",
        exitCode: result.exitCode,
        durationMs: result.durationMs,
      };
    },
  });
}

/**
 * Governed Python Script Runner (`exec.python`).
 * Runs Python code safely within the isolated sandbox environment.
 */
export async function runGovernedPython(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  script: string;
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<ExecutionToolResult> {
  const sandbox = new TaskSandbox(p.taskId, p.env.artifactDir ? `${p.env.artifactDir}/sandboxes` : "./data/sandboxes");
  await sandbox.init();
  const scriptName = `script_${Date.now()}.py`;
  await sandbox.writeFile(scriptName, p.script);

  const checkInterlock = async () => {
    const interlock = await repo.getInterlock(p.db);
    return interlock.killSwitch || interlock.circuitOpen;
  };

  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "sandboxed_python_execution",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "exec.python",
    effect: async () => {
      const result = p.env.executorRequired
        ? await executeInRemoteExecutor(p.env, { taskId: p.taskId, command: "python", args: [scriptName], files: [{ path: scriptName, content: p.script }], timeoutMs: 60_000, maxOutputBytes: p.env.maxBudgetBytes })
        : await sandbox.execute(`python "${scriptName}"`, [], {
            checkInterlock,
            timeoutMs: 60_000,
            maxOutputBytes: p.env.maxBudgetBytes,
          });

      const output = [
        result.stdout.trim(),
        result.stderr.trim() ? `[stderr]\n${result.stderr.trim()}` : "",
      ].filter(Boolean).join("\n\n");

      return {
        success: result.exitCode === 0,
        output: output || "(python executed with empty output)",
        exitCode: result.exitCode,
        durationMs: result.durationMs,
      };
    },
  });
}

/**
 * Governed File Read (`file.read`).
 * Reads a file confined strictly to the task's sandbox jail.
 */
export async function runGovernedFileRead(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  filePath: string;
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<{ content: string }> {
  const sandbox = new TaskSandbox(p.taskId, p.env.artifactDir ? `${p.env.artifactDir}/sandboxes` : "./data/sandboxes");
  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "file_read_admission",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "file.read",
    effect: async () => {
      const content = await sandbox.readFile(p.filePath);
      return { content };
    },
  });
}

/**
 * Governed File Write (`file.write`).
 * Writes a file confined strictly to the task's sandbox jail.
 */
export async function runGovernedFileWrite(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  filePath: string;
  content: string;
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<{ writtenBytes: number }> {
  const sandbox = new TaskSandbox(p.taskId, p.env.artifactDir ? `${p.env.artifactDir}/sandboxes` : "./data/sandboxes");
  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "file_write_admission",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "file.write",
    effect: async () => {
      await sandbox.writeFile(p.filePath, p.content);
      return { writtenBytes: Buffer.byteLength(p.content, "utf8") };
    },
  });
}

/**
 * Governed File List (`file.read`).
 */
export async function runGovernedFileList(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  dirPath?: string;
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<{ files: string[] }> {
  const sandbox = new TaskSandbox(p.taskId, p.env.artifactDir ? `${p.env.artifactDir}/sandboxes` : "./data/sandboxes");
  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "file_list_admission",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "file.list",
    effect: async () => {
      const files = await sandbox.listFiles(p.dirPath ?? ".");
      return { files };
    },
  });
}
