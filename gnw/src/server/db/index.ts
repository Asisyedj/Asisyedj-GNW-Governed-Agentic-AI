import fs from "node:fs";
import path from "node:path";
import { ENV, type Env } from "../env.js";
import { schemaStatements } from "./schema.js";

export type Dialect = "sqlite" | "postgres";

export class UniqueViolation extends Error {
  constructor(message = "unique_violation") {
    super(message);
    this.name = "UniqueViolation";
  }
}

export interface Db {
  dialect: Dialect;
  all<T = Record<string, unknown>>(sql: string, params?: unknown[]): Promise<T[]>;
  get<T = Record<string, unknown>>(sql: string, params?: unknown[]): Promise<T | undefined>;
  run(sql: string, params?: unknown[]): Promise<{ changes: number }>;
  insert(sql: string, params?: unknown[]): Promise<number>;
  transaction<T>(fn: (tx: Db) => Promise<T>): Promise<T>;
  close(): Promise<void>;
}

/** `?` placeholders are the shared dialect; postgres gets $n rewriting. */
function toPgSql(sql: string) {
  let index = 0;
  return sql.replace(/\?/g, () => `$${++index}`);
}

function isUniqueViolation(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  const code = (error as { code?: string } | null)?.code;
  return code === "23505" || /UNIQUE constraint failed/i.test(message);
}

async function createSqlite(url: string): Promise<Db> {
  const { default: SqliteDatabase } = await import("better-sqlite3");
  const filename = url === "file::memory:" || url === ":memory:" ? ":memory:" : url.replace(/^file:/, "");
  if (filename !== ":memory:") fs.mkdirSync(path.dirname(path.resolve(filename)), { recursive: true });
  const handle = new SqliteDatabase(filename);
  handle.pragma("journal_mode = WAL");
  handle.pragma("foreign_keys = ON");
  handle.pragma("busy_timeout = 5000");

  const guard = <T>(fn: () => T): T => {
    try {
      return fn();
    } catch (error) {
      if (isUniqueViolation(error)) throw new UniqueViolation();
      throw error;
    }
  };

  return {
    dialect: "sqlite",
    async all<T>(sql: string, params: unknown[] = []) {
      return guard(() => handle.prepare(sql).all(...(params as never[])) as T[]);
    },
    async get<T>(sql: string, params: unknown[] = []) {
      return guard(() => handle.prepare(sql).get(...(params as never[])) as T | undefined);
    },
    async run(sql: string, params: unknown[] = []) {
      const result = guard(() => handle.prepare(sql).run(...(params as never[])));
      return { changes: result.changes };
    },
    async insert(sql: string, params: unknown[] = []) {
      const result = guard(() => handle.prepare(sql).run(...(params as never[])));
      return Number(result.lastInsertRowid);
    },
    async transaction<T>(fn: (tx: Db) => Promise<T>) {
      handle.exec("BEGIN IMMEDIATE");
      try { const value = await fn(this as unknown as Db); handle.exec("COMMIT"); return value; }
      catch (error) { try { handle.exec("ROLLBACK"); } catch {} throw error; }
    },
    async close() { handle.close(); },
  };
}

async function createPostgres(url: string): Promise<Db> {
  const { default: pg } = await import("pg");
  const pool = new pg.Pool({
    connectionString: url,
    max: 10,
    idleTimeoutMillis: 30_000,
    ssl: /sslmode=(require|verify-full)/i.test(url) ? { rejectUnauthorized: true } : undefined,
  });

  const query = async (sql: string, params: unknown[]) => {
    try {
      return await pool.query(toPgSql(sql), params as never[]);
    } catch (error) {
      if (isUniqueViolation(error)) throw new UniqueViolation();
      throw error;
    }
  };

  return {
    dialect: "postgres",
    async all<T>(sql: string, params: unknown[] = []) {
      return (await query(sql, params)).rows as T[];
    },
    async get<T>(sql: string, params: unknown[] = []) {
      return (await query(sql, params)).rows[0] as T | undefined;
    },
    async run(sql: string, params: unknown[] = []) {
      const result = await query(sql, params);
      return { changes: result.rowCount ?? 0 };
    },
    async insert(sql: string, params: unknown[] = []) {
      const result = await query(`${sql} RETURNING id`, params);
      return Number(result.rows[0].id);
    },
    async transaction<T>(fn: (tx: Db) => Promise<T>) {
      const client = await pool.connect();
      const txDb: Db = {
        dialect: "postgres",
        all: async <R>(sql: string, params: unknown[] = []) => (await client.query(toPgSql(sql), params as never[])).rows as R[],
        get: async <R>(sql: string, params: unknown[] = []) => (await client.query(toPgSql(sql), params as never[])).rows[0] as R | undefined,
        run: async (sql: string, params: unknown[] = []) => ({ changes: (await client.query(toPgSql(sql), params as never[])).rowCount ?? 0 }),
        insert: async (sql: string, params: unknown[] = []) => Number((await client.query(`${toPgSql(sql)} RETURNING id`, params as never[])).rows[0].id),
        transaction: async <R>(nested: (tx: Db) => Promise<R>) => nested(txDb),
        close: async () => undefined,
      };
      let released = false;
      const safeRelease = () => { if (!released) { released = true; client.release(); } };
      await client.query("BEGIN");
      try { const value = await fn(txDb); await client.query("COMMIT"); return value; }
      catch (error) { try { await client.query("ROLLBACK"); } finally { safeRelease(); } throw error; }
      finally { safeRelease(); }
    },
    async close() { await pool.end(); },
  };
}

export async function createDb(url: string): Promise<Db> {
  if (url.startsWith("postgres://") || url.startsWith("postgresql://")) return createPostgres(url);
  return createSqlite(url);
}

export async function migrate(db: Db) {
  for (const statement of schemaStatements(db.dialect)) {
    await db.run(statement);
  }
  // Additive compatibility for databases created before Phase 3.
  try {
    await db.run("ALTER TABLE capability_leases ADD COLUMN interlock_generation INTEGER NOT NULL DEFAULT 0");
  } catch (error) {
    const code = (error as { code?: string } | null)?.code;
    const message = error instanceof Error ? error.message : String(error);
    if (code !== "42701" && !/duplicate column name|already exists/i.test(message)) throw error;
  }
  await db.run("INSERT INTO system_controls (key, value, updated_by, updated_at) VALUES ('interlock_generation', '0', NULL, 0) ON CONFLICT (key) DO NOTHING");
}

let instance: Promise<Db> | null = null;

/** Lazy singleton so serverless cold starts share one pool per instance. */
export function getDb(env: Env = ENV): Promise<Db> {
  if (!instance) {
    instance = (async () => {
      const db = await createDb(env.databaseUrl);
      await migrate(db);
      return db;
    })();
  }
  return instance;
}

export function resetDbForTests() {
  instance = null;
}
