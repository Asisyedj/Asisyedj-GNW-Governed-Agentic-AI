import { describe, expect, it } from "vitest";
import { createDb, migrate } from "../src/server/db/index.js";
import * as repo from "../src/server/repo.js";

describe("Phase 4 atomic effect fence and provider idempotency", () => {
  it("allows exactly one concurrent fence claimant", async () => {
    const db = await createDb("file::memory:"); await migrate(db);
    await repo.createEffectFence(db, { effectKey: "video:t:1", taskId: 1, tenant: "t", capability: "video.provider_job", actionDigest: "a", interlockGeneration: 0, fenceToken: "0:1:video:t:1", idempotencyKey: "idem-1", provider: "test" });
    const results = await Promise.all([repo.claimEffectFence(db, "video:t:1", 0), repo.claimEffectFence(db, "video:t:1", 0)]);
    expect(results.filter(Boolean)).toHaveLength(1); await db.close();
  });
  it("rejects a stale generation claim", async () => {
    const db = await createDb("file::memory:"); await migrate(db);
    await repo.createEffectFence(db, { effectKey: "video:t:2", taskId: 2, tenant: "t", capability: "video.provider_job", actionDigest: "a", interlockGeneration: 7, fenceToken: "7:2:video:t:2", idempotencyKey: "idem-2", provider: "test" });
    expect(await repo.claimEffectFence(db, "video:t:2", 8)).toBe(false); await db.close();
  });
  it("holds ambiguous provider failure for reconciliation", async () => {
    const db = await createDb("file::memory:"); await migrate(db);
    await repo.createEffectFence(db, { effectKey: "video:t:3", taskId: 3, tenant: "t", capability: "video.provider_job", actionDigest: "a", interlockGeneration: 0, fenceToken: "0:3:video:t:3", idempotencyKey: "idem-3", provider: "test" });
    expect(await repo.claimEffectFence(db, "video:t:3", 0)).toBe(true); await repo.reconcileEffectFence(db, "video:t:3", null, null);
    expect((await repo.getEffectFence(db, "video:t:3"))?.state).toBe("PENDING_RECONCILIATION"); await db.close();
  });
});
