import fs from "node:fs/promises";
import { generateKeyPairSync } from "node:crypto";
import { createDb, migrate } from "../src/server/db/index.js";
import { appendAudit } from "../src/server/audit.js";
import { exportAuditProofBundle } from "../src/server/merkle.js";

const db = await createDb("file::memory:");
await migrate(db);
await appendAudit(db, { taskId: 9001, eventType: "task_admission", decision: "ALLOW", reason: "pilot_task_created", payload: { pilot: "provider-submission" } });
await appendAudit(db, { taskId: 9001, eventType: "approval_review", decision: "ALLOW", reason: "independent_approval", payload: { actionDigest: "demo-action-digest" } });
await appendAudit(db, { taskId: 9001, eventType: "effect_result", decision: "ALLOW", reason: "external_effect_completed", payload: { replayProtected: true } });
const keys = generateKeyPairSync("ed25519", { privateKeyEncoding: { type: "pkcs8", format: "pem" }, publicKeyEncoding: { type: "spki", format: "pem" } });
const bundle = await exportAuditProofBundle(db, 9001, { issuer: "gnw-demo-issuer", privateKeyPem: keys.privateKey });
await fs.writeFile("demo-proof.gnwproof", JSON.stringify(bundle, null, 2));
await fs.writeFile("demo-issuer-public-key.pem", keys.publicKey);
await db.close();
