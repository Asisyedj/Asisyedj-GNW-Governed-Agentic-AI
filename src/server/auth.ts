import { createHash, createHmac, randomBytes, scrypt as scryptCallback, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";
import type { Request, Response } from "express";
import type { Db } from "./db/index.js";
import { ENV, type Env } from "./env.js";
import { countUsers, createUser, ensurePersonalWorkspace, findUserByEmail, findUserById, markSignedIn, setUserRole } from "./repo.js";

const scrypt = promisify(scryptCallback) as (password: string, salt: Buffer, keylen: number) => Promise<Buffer>;

export const SESSION_COOKIE = "gnw_session";
const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export type SessionUser = { id: number; email: string; name: string | null; role: "user" | "admin"; workspaceId: number; tenantKey: string };

export async function hashPassword(password: string) {
  const salt = randomBytes(16);
  const derived = await scrypt(password, salt, 64);
  return `scrypt$${salt.toString("hex")}$${derived.toString("hex")}`;
}

export async function verifyPassword(password: string, stored: string) {
  const [scheme, saltHex, hashHex] = stored.split("$");
  if (scheme !== "scrypt" || !saltHex || !hashHex) return false;
  const derived = await scrypt(password, Buffer.from(saltHex, "hex"), 64);
  const expected = Buffer.from(hashHex, "hex");
  return derived.length === expected.length && timingSafeEqual(derived, expected);
}

function sign(payload: string, secret: string) {
  return createHmac("sha256", secret).update(payload).digest("base64url");
}

export function issueSession(userId: number, secret: string = ENV.sessionSecret) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Date.now() + SESSION_TTL_MS })).toString("base64url");
  return `${payload}.${sign(payload, secret)}`;
}

export function readSession(token: string | undefined, secret: string = ENV.sessionSecret): number | null {
  if (!token) return null;
  const [payload, signature] = token.split(".");
  if (!payload || !signature) return null;
  const expected = sign(payload, secret);
  const a = Buffer.from(signature);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  try {
    const claims = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as { sub: number; exp: number };
    if (!claims.exp || claims.exp < Date.now()) return null;
    return claims.sub;
  } catch {
    return null;
  }
}

export function setSessionCookie(res: Response, token: string, env: Env = ENV) {
  res.cookie(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: env.cookieSameSite,
    secure: env.isProduction || env.cookieSameSite === "none",
    maxAge: SESSION_TTL_MS,
    path: "/",
  });
}

export function clearSessionCookie(res: Response, env: Env = ENV) {
  res.clearCookie(SESSION_COOKIE, { httpOnly: true, sameSite: env.cookieSameSite, secure: env.isProduction || env.cookieSameSite === "none", path: "/" });
}

export async function createSession(db: Db, userId: number, secret: string = ENV.sessionSecret) {
  const token = issueSession(userId, secret);
  const claims = JSON.parse(Buffer.from(token.split(".")[0], "base64url").toString("utf8")) as { exp: number };
  await db.run("INSERT INTO sessions (user_id, token_hash, issued_at, expires_at) VALUES (?, ?, ?, ?)", [userId, createHash("sha256").update(token).digest("hex"), Date.now(), claims.exp]);
  return token;
}

export async function revokeSession(db: Db, token: string | undefined) {
  if (!token) return;
  await db.run("UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL", [Date.now(), createHash("sha256").update(token).digest("hex")]);
}

export async function loadSessionUser(db: Db, req: Request, env: Env = ENV): Promise<SessionUser | null> {
  // The signed cookie is the primary channel. A bearer token carrying the same
  // signed value is accepted only when SESSION_TOKEN_IN_BODY is enabled, for
  // clients served through a proxy that cannot carry cookies.
  const header = req.get("authorization") ?? "";
  const bearer = env.sessionTokenInBody && header.toLowerCase().startsWith("bearer ") ? header.slice(7).trim() : "";
  const userId = readSession(req.cookies?.[SESSION_COOKIE], env.sessionSecret) ?? (bearer ? readSession(bearer, env.sessionSecret) : null);
  if (!userId) return null;
  const presented = req.cookies?.[SESSION_COOKIE] ?? (bearer || undefined);
  if (presented) {
    const row = await db.get<{ user_id: number; expires_at: number; revoked_at: number | null }>("SELECT user_id, expires_at, revoked_at FROM sessions WHERE token_hash = ?", [createHash("sha256").update(presented).digest("hex")]);
    if (!row || row.user_id !== userId || row.revoked_at !== null || Number(row.expires_at) <= Date.now()) return null;
  }
  const user = await findUserById(db, userId);
  if (!user) return null;
  const workspaceId = await ensurePersonalWorkspace(db, user.id, user.email);
  return { id: user.id, email: user.email, name: user.name, role: user.role, workspaceId, tenantKey: `tenant-user-${user.id}` };
}

export async function registerUser(db: Db, input: { email: string; password: string; name?: string }, env: Env = ENV) {
  const email = input.email.trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) throw new Error("invalid_email");
  if (input.password.length < 12) throw new Error("weak_password");
  const existing = await findUserByEmail(db, email);
  if (existing) throw new Error("email_taken");
  const isFirstUser = (await countUsers(db)) === 0;
  if (!isFirstUser && !env.allowSelfRegistration) throw new Error("registration_closed");
  const id = await createUser(db, { email, name: input.name ?? null, passwordHash: await hashPassword(input.password), role: isFirstUser ? "admin" : "user" });
  await ensurePersonalWorkspace(db, id, email);
  return id;
}

/** Seeds the owner account from the environment; idempotent across restarts. */
export async function bootstrapOwner(db: Db, env: Env = ENV) {
  if (!env.ownerEmail || !env.ownerPassword) return null;
  const existing = await findUserByEmail(db, env.ownerEmail);
  if (existing) {
    if (existing.role !== "admin") await setUserRole(db, existing.id, "admin");
    await ensurePersonalWorkspace(db, existing.id, existing.email);
    return existing.id;
  }
  if (env.ownerPassword.length < 12) throw new Error("OWNER_PASSWORD must be at least 12 characters");
  const id = await createUser(db, { email: env.ownerEmail, name: "Owner", passwordHash: await hashPassword(env.ownerPassword), role: "admin" });
  await ensurePersonalWorkspace(db, id, env.ownerEmail);
  return id;
}

export async function signIn(db: Db, userId: number) {
  await markSignedIn(db, userId);
}

export async function ensureGuestUser(db: Db) {
  const email = "guest@governed.agent";
  const existing = await findUserByEmail(db, email);
  if (existing) {
    if (existing.role !== "admin") await setUserRole(db, existing.id, "admin");
    await ensurePersonalWorkspace(db, existing.id, existing.email);
    return existing.id;
  }
  const id = await createUser(db, {
    email,
    name: "Guest Operator",
    passwordHash: await hashPassword("GuestDemoPass123!"),
    role: "admin",
  });
  await ensurePersonalWorkspace(db, id, email);
  return id;
}

