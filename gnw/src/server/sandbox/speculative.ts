import { randomUUID } from "node:crypto";
import { TaskSandbox, type SandboxRunResult } from "./index.js";

export interface SpeculativeExecutionResult {
  success: boolean;
  committed: boolean;
  rolledBack: boolean;
  runResult?: SandboxRunResult;
  error?: string;
  speculativeDurationMs: number;
  snapshotName: string;
  restoredFiles?: number;
  removedFiles?: number;
}

export class SpeculativeSandboxEngine {
  /**
   * Runs a potentially dangerous sandbox operation in speculative trial mode.
   * If post-execution validation fails or the process crashes, the sandbox
   * instantly and atomically rolls back to its exact pre-execution state.
   */
  async executeSpeculative(
    sandbox: TaskSandbox,
    action: () => Promise<SandboxRunResult>,
    validator?: (res: SandboxRunResult) => Promise<boolean> | boolean
  ): Promise<SpeculativeExecutionResult> {
    const startTime = Date.now();
    const snapshotName = `speculative-${Date.now()}-${randomUUID().slice(0, 8)}`;

    // 1. Take atomic snapshot of current sandbox state
    await sandbox.createSnapshot(snapshotName);

    try {
      // 2. Perform the trial action inside the sandbox
      const runResult = await action();

      // 3. Post-execution validation: process exit code, timeout check, and custom validator
      const basicPass = runResult.exitCode === 0 && !runResult.timedOut;
      let validatorPass = true;
      if (basicPass && validator) {
        validatorPass = await validator(runResult);
      }

      if (basicPass && validatorPass) {
        // Speculation succeeded: commit changes (keep sandbox state)
        return {
          success: true,
          committed: true,
          rolledBack: false,
          runResult,
          speculativeDurationMs: Date.now() - startTime,
          snapshotName,
        };
      }

      // Speculation failed: rollback cleanly
      const rollbackInfo = await sandbox.rollbackSnapshot(snapshotName);
      return {
        success: false,
        committed: false,
        rolledBack: true,
        runResult,
        error: runResult.timedOut
          ? "Execution timed out during speculative sandbox trial."
          : `Execution failed with exit code ${runResult.exitCode}. Output: ${runResult.stderr || runResult.stdout}`,
        speculativeDurationMs: Date.now() - startTime,
        snapshotName,
        restoredFiles: rollbackInfo.restoredFiles,
        removedFiles: rollbackInfo.removedFiles,
      };
    } catch (err) {
      // Catastrophic error during trial: rollback immediately
      const rollbackInfo = await sandbox.rollbackSnapshot(snapshotName);
      const detail = err instanceof Error ? err.message : String(err);
      return {
        success: false,
        committed: false,
        rolledBack: true,
        error: `Sandbox trial aborted due to exception: ${detail}`,
        speculativeDurationMs: Date.now() - startTime,
        snapshotName,
        restoredFiles: rollbackInfo.restoredFiles,
        removedFiles: rollbackInfo.removedFiles,
      };
    }
  }

  /**
   * Speculatively modifies a file and runs a verification test command.
   * If tests pass, the modification is committed. If tests fail, the file is
   * rolled back immediately, leaving the sandbox in a pristine, working state.
   */
  async speculativeWriteAndTest(
    sandbox: TaskSandbox,
    relativePath: string,
    content: string,
    testCommand: string
  ): Promise<SpeculativeExecutionResult> {
    return this.executeSpeculative(sandbox, async () => {
      await sandbox.writeFile(relativePath, content);
      return sandbox.execute(testCommand);
    });
  }
}
