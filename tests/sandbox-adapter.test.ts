import { describe, expect, it } from "vitest";
import { loadEnv } from "../src/server/env.js";
import { createSandboxAdapter, LocalSandboxAdapter, RemoteSandboxAdapter } from "../src/server/sandbox/adapter.js";
import { TaskSandbox } from "../src/server/sandbox/index.js";

const base = { NODE_ENV: "test", SESSION_SECRET: "s".repeat(48), DATABASE_URL: "file::memory:", ARTIFACT_DIR: "/tmp/gnw-adapter-tests" };

describe("Step 6 sandbox adapter boundary", () => {
  it("uses the local adapter only when remote execution is not required", () => {
    const adapter = createSandboxAdapter(loadEnv({ ...base, GNW_EXECUTOR_REQUIRED: "false" }));
    expect(adapter).toBeInstanceOf(LocalSandboxAdapter);
    expect(adapter.mode).toBe("local-test");
  });

  it("selects the remote adapter when production isolation is required", () => {
    const env = loadEnv({ ...base, NODE_ENV: "production", DATABASE_URL: "postgres://db", STORAGE_DRIVER: "s3", S3_BUCKET: "b", S3_ACCESS_KEY_ID: "a", S3_SECRET_ACCESS_KEY: "s", GNW_REQUIRE_SIGNED_GRANTS: "false", GNW_EXECUTOR_REQUIRED: "true", GNW_EXECUTOR_URL: "https://executor.example", GNW_EXECUTOR_SHARED_TOKEN: "token" });
    const adapter = createSandboxAdapter(env);
    expect(adapter).toBeInstanceOf(RemoteSandboxAdapter);
    expect(adapter.mode).toBe("remote-managed");
  });

  it("refuses to run a remote adapter when isolation is not enabled", async () => {
    const env = loadEnv({ ...base, GNW_EXECUTOR_REQUIRED: "false", GNW_EXECUTOR_URL: "https://executor.example", GNW_EXECUTOR_SHARED_TOKEN: "token" });
    const adapter = new RemoteSandboxAdapter(env);
    await expect(adapter.execute({ taskId: 1, command: "true" })).rejects.toThrow("remote_executor_not_required");
  });

  it("rejects sibling-prefix paths outside the sandbox jail", () => {
    const sandbox = new TaskSandbox(1, "/tmp/gnw-sandboxes");
    expect(() => sandbox.resolvePath("../task-10/secret.txt")).toThrow(/Access outside sandbox jail refused/);
  });
});
