import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";

export class SandboxViolation extends Error {
  constructor(public readonly code: string, message = code) {
    super(message);
    this.name = "SandboxViolation";
  }
}

export type SandboxRunResult = {
  stdout: string;
  stderr: string;
  exitCode: number | null;
  timedOut: boolean;
  durationMs: number;
};

export type SandboxOptions = {
  timeoutMs?: number;
  maxOutputBytes?: number;
  env?: Record<string, string>;
  checkInterlock?: () => Promise<boolean>;
};

const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_MAX_OUTPUT_BYTES = 2_000_000;

// Sensitive environment variables that must NEVER leak into the sandbox
const BLOCKED_ENV_VARS = [
  "SESSION_SECRET",
  "DATABASE_URL",
  "GNW_GRANT_PRIVATE_KEY_PEM",
  "GNW_GRANT_PUBLIC_KEY_PEM",
  "LLM_API_KEY",
  "VIDEO_PROVIDER_API_KEY",
  "S3_SECRET_ACCESS_KEY",
  "S3_ACCESS_KEY_ID",
  "NOTIFY_WEBHOOK_URL",
];

export class TaskSandbox {
  public readonly jailRoot: string;

  constructor(public readonly taskId: number, baseSandboxDir = "./data/sandboxes") {
    this.jailRoot = path.resolve(baseSandboxDir, `task-${taskId}`);
  }

  /** Ensures the sandbox workspace directory exists. */
  async init() {
    await fs.mkdir(this.jailRoot, { recursive: true });
  }

  /**
   * Resolves a path strictly inside the sandbox jail.
   * Prevents directory traversal attacks (e.g. `../../etc/passwd`).
   */
  resolvePath(relativePath: string): string {
    const safePath = path.resolve(this.jailRoot, relativePath.replace(/^(\/|\\)+/, ""));
    const relative = path.relative(this.jailRoot, safePath);
    if (relative.startsWith("..") || path.isAbsolute(relative)) {
      throw new SandboxViolation("directory_traversal_denied", `Access outside sandbox jail refused: ${relativePath}`);
    }
    return safePath;
  }

  /**
   * Sanitizes process environment by scrubbing host secrets.
   */
  cleanEnvironment(customEnv: Record<string, string> = {}): NodeJS.ProcessEnv {
    const clean: NodeJS.ProcessEnv = {};
    for (const [key, value] of Object.entries(process.env)) {
      if (!BLOCKED_ENV_VARS.includes(key)) {
        clean[key] = value;
      }
    }
    return { ...clean, ...customEnv, GNW_TASK_ID: String(this.taskId), GNW_SANDBOX: "true" };
  }

  /**
   * Executes a command within the jailed working directory.
   * Enforces timeout, byte limits, and kill-switch termination.
   */
  async execute(command: string, args: string[] = [], options: SandboxOptions = {}): Promise<SandboxRunResult> {
    await this.init();
    if (options.checkInterlock && (await options.checkInterlock())) {
      throw new SandboxViolation("safety_interlock", "Kill switch engaged; sandbox execution refused.");
    }

    const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    const maxOutputBytes = options.maxOutputBytes ?? DEFAULT_MAX_OUTPUT_BYTES;
    const env = this.cleanEnvironment(options.env);

    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      let timedOut = false;
      let totalBytes = 0;

      // Use system shell for broad command compatibility
      const child = spawn(command, args, {
        cwd: this.jailRoot,
        env,
        shell: true,
        windowsHide: true,
      });

      const stdoutChunks: Buffer[] = [];
      const stderrChunks: Buffer[] = [];

      const timer = setTimeout(() => {
        timedOut = true;
        child.kill("SIGKILL");
      }, timeoutMs);

      // Kill-switch polling interval during long-running commands
      let interlockInterval: NodeJS.Timeout | undefined;
      if (options.checkInterlock) {
        interlockInterval = setInterval(async () => {
          try {
            if (options.checkInterlock && (await options.checkInterlock())) {
              child.kill("SIGKILL");
            }
          } catch {
            child.kill("SIGKILL");
          }
        }, 500);
      }

      child.stdout?.on("data", chunk => {
        const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        totalBytes += buf.byteLength;
        if (totalBytes > maxOutputBytes) {
          child.kill("SIGKILL");
          return;
        }
        stdoutChunks.push(buf);
      });

      child.stderr?.on("data", chunk => {
        const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        totalBytes += buf.byteLength;
        if (totalBytes > maxOutputBytes) {
          child.kill("SIGKILL");
          return;
        }
        stderrChunks.push(buf);
      });

      child.on("error", err => {
        clearTimeout(timer);
        if (interlockInterval) clearInterval(interlockInterval);
        reject(err);
      });

      child.on("close", code => {
        clearTimeout(timer);
        if (interlockInterval) clearInterval(interlockInterval);
        resolve({
          stdout: Buffer.concat(stdoutChunks).toString("utf8"),
          stderr: Buffer.concat(stderrChunks).toString("utf8"),
          exitCode: code,
          timedOut,
          durationMs: Date.now() - startTime,
        });
      });
    });
  }

  /** Safe jailed file read. */
  async readFile(relativePath: string): Promise<string> {
    const fullPath = this.resolvePath(relativePath);
    return fs.readFile(fullPath, "utf8");
  }

  /** Safe jailed file write. */
  async writeFile(relativePath: string, content: string): Promise<void> {
    const fullPath = this.resolvePath(relativePath);
    await fs.mkdir(path.dirname(fullPath), { recursive: true });
    await fs.writeFile(fullPath, content, "utf8");
  }

  /** List directory contents within jail. */
  async listFiles(relativePath = "."): Promise<string[]> {
    const fullPath = this.resolvePath(relativePath);
    if (!fsSync.existsSync(fullPath)) return [];
    return fs.readdir(fullPath);
  }

  /** Clean up task sandbox directory. */
  async destroy(): Promise<void> {
    if (fsSync.existsSync(this.jailRoot)) {
      await fs.rm(this.jailRoot, { recursive: true, force: true });
    }
  }

  private snapshots: Map<string, Map<string, string>> = new Map();

  /**
   * Creates an atomic in-memory snapshot of all files currently in the sandbox.
   * Enables instant rollback if a subsequent execution fails or produces bad output.
   */
  async createSnapshot(snapshotName = "default"): Promise<{ name: string; fileCount: number; timestamp: number }> {
    await this.init();
    const snapshotMap = new Map<string, string>();

    const traverse = async (dir: string) => {
      const entries = await fs.readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          await traverse(full);
        } else if (entry.isFile()) {
          const rel = path.relative(this.jailRoot, full);
          const content = await fs.readFile(full, "utf8");
          snapshotMap.set(rel, content);
        }
      }
    };

    await traverse(this.jailRoot);
    this.snapshots.set(snapshotName, snapshotMap);
    return { name: snapshotName, fileCount: snapshotMap.size, timestamp: Date.now() };
  }

  /**
   * Instantly rolls back the sandbox filesystem to a previously created snapshot.
   * Deletes any files created since the snapshot and restores original file contents.
   */
  async rollbackSnapshot(snapshotName = "default"): Promise<{ rolledBack: boolean; restoredFiles: number; removedFiles: number }> {
    const snapshot = this.snapshots.get(snapshotName);
    if (!snapshot) {
      throw new SandboxViolation("snapshot_not_found", `Snapshot '${snapshotName}' does not exist.`);
    }

    let removed = 0;
    let restored = 0;

    // 1. Delete files in sandbox that were not in snapshot
    const traverse = async (dir: string) => {
      if (!fsSync.existsSync(dir)) return;
      const entries = await fs.readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          await traverse(full);
        } else if (entry.isFile()) {
          const rel = path.relative(this.jailRoot, full);
          if (!snapshot.has(rel)) {
            await fs.rm(full, { force: true });
            removed++;
          }
        }
      }
    };
    await traverse(this.jailRoot);

    // 2. Restore/overwrite files from snapshot
    for (const [rel, content] of snapshot.entries()) {
      const target = this.resolvePath(rel);
      await fs.mkdir(path.dirname(target), { recursive: true });
      await fs.writeFile(target, content, "utf8");
      restored++;
    }

    return { rolledBack: true, restoredFiles: restored, removedFiles: removed };
  }

  /** Checks if a named snapshot exists. */
  hasSnapshot(snapshotName = "default"): boolean {
    return this.snapshots.has(snapshotName);
  }
}
