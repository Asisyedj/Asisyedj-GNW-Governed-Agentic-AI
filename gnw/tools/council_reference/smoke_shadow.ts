import { loadEnv } from "../../src/server/env.js";
import { createDb, migrate } from "../../src/server/db/index.js";
import { buildShadowEnvelope, runCouncilShadow } from "../../src/server/council/orchestrator.js";

const env = loadEnv({ NODE_ENV: "test", DATABASE_URL: "file::memory:", SESSION_SECRET: "s".repeat(48), GNW_COUNCIL_MODE: "shadow" });
const db = await createDb(env.databaseUrl);
await migrate(db);
const result = await runCouncilShadow({
  db,
  env,
  sourceTaskId: 1,
  actorUserId: 1,
  envelope: buildShadowEnvelope({ sourceTaskId: 1, actorUserId: 1, purpose: "smoke", classification: "internal", promptDigest: "a".repeat(64) }),
});
console.log(JSON.stringify(result));
await db.close();
