import { createDb, migrate } from "../src/server/db/index.js";
import pg from "pg";

const url = process.env.DATABASE_URL;
if (!url || !(url.startsWith("postgres://") || url.startsWith("postgresql://"))) throw new Error("DATABASE_URL must be a PostgreSQL URL");
const db = await createDb(url);
await migrate(db);
const suffix = Date.now();
const tenantA = db.withTenant(`gnw-rls-a-${suffix}`);
const tenantB = db.withTenant(`gnw-rls-b-${suffix}`);
const workspaceA = await tenantA.insert("INSERT INTO workspaces (tenant_key, name, created_by, created_at) VALUES (?, ?, ?, ?)", [`gnw-rls-a-${suffix}`, "A", 1, Date.now()]);
const workspaceB = await tenantB.insert("INSERT INTO workspaces (tenant_key, name, created_by, created_at) VALUES (?, ?, ?, ?)", [`gnw-rls-b-${suffix}`, "B", 2, Date.now()]);
const taskA = await tenantA.insert("INSERT INTO tasks (workspace_id, created_by, title, prompt, purpose, classification, status, selected_agents, budget_tokens, budget_bytes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [workspaceA, 1, "A task", "p", "internal", "internal", "queued", "[]", 10, 10, Date.now(), Date.now()]);
const taskB = await tenantB.insert("INSERT INTO tasks (workspace_id, created_by, title, prompt, purpose, classification, status, selected_agents, budget_tokens, budget_bytes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [workspaceB, 2, "B task", "p", "internal", "internal", "queued", "[]", 10, 10, Date.now(), Date.now()]);
const tenantARows = await tenantA.all("SELECT id, workspace_id FROM tasks ORDER BY id");
const tenantBRows = await tenantB.all("SELECT id, workspace_id FROM tasks ORDER BY id");
const unscopedRows = await db.all("SELECT id, workspace_id FROM tasks ORDER BY id");
let crossTenantInsertDenied = false;
try {
  await tenantB.insert("INSERT INTO tasks (workspace_id, created_by, title, prompt, purpose, classification, status, selected_agents, budget_tokens, budget_bytes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [workspaceA, 2, "bad", "p", "internal", "internal", "queued", "[]", 10, 10, Date.now(), Date.now()]);
} catch { crossTenantInsertDenied = true; }
const client = new pg.Client({ connectionString: url });
await client.connect();
const rls = await client.query("SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('workspaces','tasks','messages','agent_runs','approvals','capability_leases','effect_fences','video_jobs','artifacts','notifications') ORDER BY relname");
await client.end();
const report = { schema: "GNW.PostgresRlsGate.v1", tenantARows, tenantBRows, unscopedRows, crossTenantInsertDenied, rls: rls.rows };
console.log(JSON.stringify(report, null, 2));
if (tenantARows.length !== 1 || tenantARows[0].id !== taskA) throw new Error("tenant_a_visibility_failed");
if (tenantBRows.length !== 1 || tenantBRows[0].id !== taskB) throw new Error("tenant_b_visibility_failed");
if (unscopedRows.length !== 0) throw new Error("unscoped_visibility_not_denied");
if (!crossTenantInsertDenied) throw new Error("cross_tenant_insert_not_denied");
if (rls.rows.length !== 10 || rls.rows.some(row => !row.relrowsecurity || !row.relforcerowsecurity)) throw new Error("force_rls_not_enabled_on_all_tenant_tables");
await db.close();
