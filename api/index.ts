import type { IncomingMessage, ServerResponse } from "node:http";
import { createApp } from "../src/server/app.js";
import { getDb, migrate } from "../src/server/db/index.js";
import { bootstrapOwner } from "../src/server/auth.js";
import { loadEnv } from "../src/server/env.js";
import type { Express } from "express";

let appPromise: Promise<Express> | null = null;

async function initServer(): Promise<Express> {
  const env = loadEnv(process.env);
  const db = await getDb(env);
  
  // Ensure schema migrations and initial owner exist
  await migrate(db).catch(err => {
    console.warn("[Vercel-Init] Database migration warning:", err);
  });
  
  if (env.ownerEmail && env.ownerPassword) {
    await bootstrapOwner(db, env).catch(err => {
      console.warn("[Vercel-Init] Owner bootstrap warning:", err);
    });
  }

  return createApp(env, Promise.resolve(db));
}

export default async function handler(req: IncomingMessage, res: ServerResponse) {
  if (!appPromise) {
    appPromise = initServer();
  }
  const app = await appPromise;
  return app(req, res);
}
