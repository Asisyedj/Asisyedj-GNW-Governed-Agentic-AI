import { randomBytes } from "node:crypto";
import path from "node:path";
import fs from "node:fs";
import express, { type NextFunction, type Request, type Response } from "express";
import cookieParser from "cookie-parser";
import { z } from "zod";
import { ENV, readinessReport, type Env } from "./env.js";
import { getDb, type Db } from "./db/index.js";
import { listAudit, verifyAuditChain, appendAudit } from "./audit.js";
import * as repo from "./repo.js";
import { clearSessionCookie, createSession, ensureGuestUser, hashPassword, loadSessionUser, registerUser, revokeSession, setSessionCookie, signIn, verifyPassword, type SessionUser } from "./auth.js";
import { authorizeArtifactStorage, buildGrant, governanceService, runTask, sha256 } from "./orchestrator.js";
import { submitApprovedVideoJob, pollVideoJob } from "./video.js";
import { storagePut } from "./storage.js";
import { signGrant, canonicalize } from "./security.js";
import { executeExternal } from "./execution.js";
import { runGovernedCommand, runGovernedPython, runGovernedFileRead, runGovernedFileWrite, runGovernedFileList } from "./tools/executor.js";
import { runGovernedBrowse } from "./tools/browser.js";
import { runGovernedVisualInspect, runGovernedBrowserAction } from "./tools/visual-browser.js";
import { runGovernedGitStatus, runGovernedGitDiff, runGovernedGitCommit, runGovernedGitHubCreatePR } from "./tools/git.js";
import { runGovernedMemoryStore, runGovernedMemoryQuery } from "./tools/memory.js";
import { runGovernedFindSymbols, runGovernedFindDefinition } from "./tools/code-intel.js";
import { analyzeCommandRisk } from "./security/guard.js";
import { exportAuditProofBundle, verifyMerkleProof } from "./merkle.js";
import { MultiAgentQuorumEngine } from "./quorum.js";
import { TrajectoryInvariantEngine } from "./invariants.js";
import { createDefaultSkillRegistry } from "./skills/index.js";
import { CLASSIFICATIONS, SPECIALIST_AGENTS } from "../shared/types.js";

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      db: Db;
      user?: SessionUser;
    }
  }
}

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

const asyncRoute = (handler: (req: Request, res: Response) => Promise<unknown>) => (req: Request, res: Response, next: NextFunction) => {
  handler(req, res).catch(next);
};

export async function createApp(env: Env = ENV, dbPromise: Promise<Db> = getDb(env)) {
  const db = await dbPromise;
  const app = express();
  app.disable("x-powered-by");
  app.set("trust proxy", 1);

  app.use((_req, res, next) => {
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("X-Frame-Options", "DENY");
    res.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
    res.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
    res.setHeader("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'");
    if (env.isProduction) res.setHeader("Strict-Transport-Security", "max-age=63072000; includeSubDomains");
    next();
  });

  // Only enabled when the client is deliberately hosted on another origin.
  // A single allowed origin, credentials on, and the custom header the CSRF
  // guard already requires — no wildcard is ever emitted.
  if (env.corsOrigin) {
    const allowed = env.corsOrigin.split(",").map(value => value.trim()).filter(Boolean);
    app.use((req, res, next) => {
      const origin = req.get("origin");
      if (origin && allowed.includes(origin)) {
        res.setHeader("Access-Control-Allow-Origin", origin);
        res.setHeader("Vary", "Origin");
        res.setHeader("Access-Control-Allow-Credentials", "true");
        res.setHeader("Access-Control-Allow-Headers", "content-type, x-gnw-client, authorization");
        res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
        if (req.method === "OPTIONS") return res.status(204).end();
      }
      next();
    });
  }

  app.use(express.json({ limit: "2mb" }));
  app.use(cookieParser());
  app.use((req, _res, next) => {
    req.db = db;
    next();
  });

  // Cross-site request forgery guard: same-site cookie plus a header that a
  // cross-origin form post cannot set without a CORS preflight we never allow.
  app.use("/api", (req, res, next) => {
    if (MUTATING.has(req.method) && !req.path.startsWith("/auth/") && req.get("x-gnw-client") !== "web") {
      return res.status(403).json({ error: "csrf_header_required" });
    }
    next();
  });

  const auth = (): express.RequestHandler => async (req, res, next) => {
    try {
      const user = await loadSessionUser(db, req, env);
      if (!user) return res.status(401).json({ error: "unauthenticated" });
      req.user = user;
      next();
    } catch (error) {
      next(error);
    }
  };

  const adminOnly = (): express.RequestHandler => (req, res, next) => {
    if (req.user?.role !== "admin") return res.status(403).json({ error: "admin_required" });
    next();
  };

  /* ------------------------------------------------------------- health */

  app.get("/api/health", (_req, res) => res.status(200).json({ status: "ok", service: "gnw-governed-agent", version: "4.0.0", timestamp: new Date().toISOString() }));

  app.get("/api/ready", asyncRoute(async (_req, res) => {
    const report = readinessReport(env);
    let database: "ok" | "missing" = "ok";
    try {
      await db.get("SELECT 1 AS ok");
    } catch {
      database = "missing";
    }
    const checks = { ...report.checks, database };
    const ready = Object.values(checks).every(value => value !== "missing");
    res.status(ready ? 200 : 503).json({ ready, checks, notes: report.notes, timestamp: new Date().toISOString() });
  }));

  /* --------------------------------------------------------------- auth */

  const credentials = z.object({ email: z.string().email().max(320), password: z.string().min(8).max(200), name: z.string().max(120).optional() });

  app.post("/api/auth/register", asyncRoute(async (req, res) => {
    const parsed = credentials.safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input", detail: parsed.error.flatten() });
    try {
      const userId = await registerUser(db, parsed.data, env);
      await signIn(db, userId);
      const token = await createSession(db, userId, env.sessionSecret);
      setSessionCookie(res, token, env);
      await appendAudit(db, { actorUserId: userId, eventType: "user_registered", decision: "ALLOW", reason: "account_created", payload: { email: parsed.data.email } });
      const created = await repo.findUserById(db, userId);
      const workspaceId = await repo.ensurePersonalWorkspace(db, userId, parsed.data.email);
      return res.status(201).json({ user: { id: userId, email: parsed.data.email, name: created?.name ?? null, role: created?.role ?? "user", workspaceId, tenantKey: `tenant-user-${userId}` }, ...(env.sessionTokenInBody ? { token } : {}) });
    } catch (error) {
      const code = error instanceof Error ? error.message : "registration_failed";
      const status = code === "registration_closed" ? 403 : 400;
      return res.status(status).json({ error: code });
    }
  }));

  app.post("/api/auth/login", asyncRoute(async (req, res) => {
    const parsed = credentials.safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });
    const email = parsed.data.email.trim().toLowerCase();
    const ip = req.ip ?? "unknown";
    if ((await repo.recentFailedLogins(db, email)) >= 8) {
      await appendAudit(db, { eventType: "login_throttled", decision: "DENY", reason: "too_many_attempts", payload: { email } });
      return res.status(429).json({ error: "too_many_attempts" });
    }
    const user = await repo.findUserByEmail(db, email);
    const ok = user ? await verifyPassword(parsed.data.password, user.password_hash) : false;
    await repo.recordLoginAttempt(db, email, ip, ok);
    if (!user || !ok) {
      await appendAudit(db, { eventType: "login_failed", decision: "DENY", reason: "invalid_credentials", payload: { email } });
      return res.status(401).json({ error: "invalid_credentials" });
    }
    await signIn(db, user.id);
    await repo.ensurePersonalWorkspace(db, user.id, user.email);
    const token = await createSession(db, user.id, env.sessionSecret);
    setSessionCookie(res, token, env);
    await appendAudit(db, { actorUserId: user.id, eventType: "login_succeeded", decision: "ALLOW", reason: "session_issued", payload: { email } });
    return res.json({ user: { id: user.id, email: user.email, name: user.name, role: user.role }, ...(env.sessionTokenInBody ? { token } : {}) });
  }));

  // Guest access is intentionally removed. No unauthenticated request may
  // create an admin session or receive a tenant identity.
  app.post("/api/auth/guest", (_req, res) => res.status(410).json({ error: "guest_access_disabled" }));

  // A Google credential is never decoded and trusted locally. Until a real
  // OIDC verifier with issuer/audience/signature/nonce checks is configured,
  // this endpoint must fail closed rather than accept a spoofable JWT body.
  app.post("/api/auth/google", (_req, res) => res.status(503).json({ error: "google_oidc_verifier_not_configured" }));

  app.post("/api/auth/logout", asyncRoute(async (req, res) => {
    await revokeSession(db, req.cookies?.gnw_session);
    clearSessionCookie(res, env);
    res.json({ success: true });
  }));

  app.get("/api/auth/me", asyncRoute(async (req, res) => {
    const user = await loadSessionUser(db, req, env);
    const bootstrap = (await repo.countUsers(db)) === 0;
    res.json({ user, bootstrap, allowSelfRegistration: env.allowSelfRegistration });
  }));

  /* ---------------------------------------------------------- workspace */

  app.get("/api/workspace/summary", auth(), asyncRoute(async (req, res) => {
    const user = req.user!;
    await repo.expireApprovals(db);
    const [tasks, approvals, interlock, notifications] = await Promise.all([
      repo.listTasks(db, user.workspaceId),
      repo.listApprovals(db, user.workspaceId),
      repo.getInterlock(db),
      repo.listNotifications(db, user.id, 20),
    ]);
    res.json({
      user,
      agents: SPECIALIST_AGENTS,
      tasks,
      approvals,
      interlock,
      notifications,
      readiness: readinessReport(env),
    });
  }));

  /* -------------------------------------------------------------- tasks */

  const taskInput = z.object({
    prompt: z.string().min(8).max(12000),
    purpose: z.string().min(2).max(120),
    classification: z.enum(CLASSIFICATIONS).default("internal"),
    selectedAgents: z.array(z.enum(SPECIALIST_AGENTS)).min(1).max(5),
    budgetTokens: z.number().int().min(500).max(env.maxBudgetTokens).default(4000),
    budgetBytes: z.number().int().min(512).max(env.maxBudgetBytes).default(4096),
  });

  app.get("/api/tasks", auth(), asyncRoute(async (req, res) => {
    res.json({ tasks: await repo.listTasks(db, req.user!.workspaceId) });
  }));

  app.post("/api/tasks", auth(), asyncRoute(async (req, res) => {
    const parsed = taskInput.safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input", detail: parsed.error.flatten() });
    const interlock = await repo.getInterlock(db);
    if (interlock.killSwitch || interlock.circuitOpen) {
      await appendAudit(db, { actorUserId: req.user!.id, eventType: "task_admission", decision: "STOP", reason: "safety_interlock", payload: { purpose: parsed.data.purpose } });
      return res.status(423).json({ error: "safety_interlock", detail: "The kill switch or circuit breaker is engaged. No task can be admitted." });
    }
    const result = await runTask(db, req.user!, parsed.data, env);
    return res.status(201).json(result);
  }));

  app.get("/api/tasks/:taskId", auth(), asyncRoute(async (req, res) => {
    const taskId = Number(req.params.taskId);
    if (!Number.isInteger(taskId) || taskId <= 0) return res.status(400).json({ error: "invalid_task_id" });
    const task = await repo.getTaskForUser(db, taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });
    const [messages, runs, approvals, videoJobs, artifacts, audit] = await Promise.all([
      repo.listMessages(db, taskId),
      repo.listAgentRuns(db, taskId),
      repo.listApprovals(db, req.user!.workspaceId),
      repo.listVideoJobs(db, taskId),
      repo.listArtifacts(db, taskId),
      listAudit(db, taskId),
    ]);
    return res.json({ task, messages, runs, approvals: approvals.filter(item => item.task_id === taskId), videoJobs, artifacts, audit });
  }));

  /* ---------------------------------------------------------- approvals */

  app.get("/api/approvals", auth(), asyncRoute(async (req, res) => {
    await repo.expireApprovals(db);
    res.json({ approvals: await repo.listApprovals(db, req.user!.workspaceId) });
  }));

  app.post("/api/approvals/:approvalId/review", auth(), asyncRoute(async (req, res) => {
    const approvalId = Number(req.params.approvalId);
    const parsed = z.object({ status: z.enum(["approved", "denied"]) }).safeParse(req.body);
    if (!Number.isInteger(approvalId) || !parsed.success) return res.status(400).json({ error: "invalid_input" });
    await repo.expireApprovals(db);
    const approval = await repo.getApproval(db, approvalId);
    if (!approval) return res.status(404).json({ error: "approval_not_found" });
    const task = await repo.getTaskForUser(db, approval.task_id, req.user!.workspaceId);
    if (!task) return res.status(403).json({ error: "tenant_binding" });
    if (approval.requested_by === req.user!.id && req.user!.role !== "admin") {
      // Separation of duties: a requester cannot self-approve unless they are
      // the workspace admin acting as the accountable reviewer.
      await appendAudit(db, { taskId: approval.task_id, actorUserId: req.user!.id, eventType: "approval_review", decision: "DENY", reason: "separation_of_duties", payload: { approvalId } });
      return res.status(403).json({ error: "separation_of_duties" });
    }
    const updated = await repo.reviewApproval(db, approvalId, req.user!.id, parsed.data.status);
    if (!updated) return res.status(409).json({ error: "approval_not_pending_or_expired" });
    await appendAudit(db, { taskId: approval.task_id, actorUserId: req.user!.id, eventType: "approval_review", decision: parsed.data.status === "approved" ? "ALLOW" : "DENY", reason: `approval_${parsed.data.status}`, payload: { approvalId, actionDigest: approval.action_digest } });
    if (parsed.data.status === "denied" && approval.video_job_id) {
      await repo.updateVideoJob(db, approval.video_job_id, { status: "stopped", errorMessage: "approval_denied" });
      await repo.updateTaskStatus(db, approval.task_id, "denied");
    }
    return res.json({ success: true, status: parsed.data.status });
  }));

  /* -------------------------------------------------------------- video */

  app.post("/api/video/submit", auth(), asyncRoute(async (req, res) => {
    const parsed = z.object({ approvalId: z.number().int().positive() }).safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });
    const result = await submitApprovedVideoJob(db, req.user!, parsed.data.approvalId, env);
    if (!result.ok) return res.status(result.status === "STOP" ? 423 : 403).json(result);
    return res.json(result);
  }));

  app.get("/api/video/:jobId", auth(), asyncRoute(async (req, res) => {
    const jobId = Number(req.params.jobId);
    if (!Number.isInteger(jobId)) return res.status(400).json({ error: "invalid_job_id" });
    const job = await repo.getVideoJob(db, jobId);
    if (!job) return res.status(404).json({ error: "video_job_not_found" });
    const task = await repo.getTaskForUser(db, job.task_id, req.user!.workspaceId);
    if (!task) return res.status(403).json({ error: "tenant_binding" });
    const refreshed = await pollVideoJob(db, req.user!, jobId, env);
    return res.json({ job: refreshed ?? job, artifacts: await repo.listArtifacts(db, job.task_id) });
  }));

  /* ---------------------------------------------------------- artifacts */

  app.post("/api/artifacts", auth(), asyncRoute(async (req, res) => {
    const parsed = z
      .object({
        taskId: z.number().int().positive(),
        kind: z.enum(["input", "brief", "script", "storyboard", "video", "result"]),
        content: z.string().min(1).max(200_000),
        contentType: z.string().min(3).max(160),
      })
      .safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });
    const task = await repo.getTaskForUser(db, parsed.data.taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });
    const digest = sha256(parsed.data.content);
    const storageDecision = await authorizeArtifactStorage(db, req.user!, task.id, task.classification, digest, env);
    if (!storageDecision.allowed || !storageDecision.capabilityLease) {
      return res.status(storageDecision.status === "STOP" ? 503 : 403).json({ error: storageDecision.reason });
    }
    const stored = await executeExternal({
      db, env, taskId: task.id, actorUserId: req.user!.id, eventType: "artifact_storage", actionDigest: storageDecision.actionDigest, capabilityLease: storageDecision.capabilityLease, capability: "artifact.storage",
      effect: () => storagePut(`tasks/${task.id}/${parsed.data.kind}/${digest}.artifact`, parsed.data.content, parsed.data.contentType, env),
    });
    await repo.createArtifact(db, {
      taskId: task.id,
      kind: parsed.data.kind,
      storageKey: stored.key,
      storageUrl: stored.url,
      contentType: parsed.data.contentType,
      byteSize: stored.byteSize,
      sha256: digest,
      createdBy: req.user!.id,
    });
    await appendAudit(db, { taskId: task.id, actorUserId: req.user!.id, eventType: "artifact_registered", decision: "ALLOW", reason: "external_storage_reference_created", payload: { kind: parsed.data.kind, storageKey: stored.key, sha256: digest } });
    return res.status(201).json({ key: stored.key, url: stored.url, sha256: digest, byteSize: stored.byteSize, driver: stored.driver });
  }));

  /* ------------------------------------------- governed execution & tools */

  app.post("/api/tasks/:taskId/execute", auth(), asyncRoute(async (req, res) => {
    const taskId = Number(req.params.taskId);
    if (!Number.isInteger(taskId)) return res.status(400).json({ error: "invalid_task_id" });
    const task = await repo.getTaskForUser(db, taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });

    const parsed = z
      .object({
        operation: z.enum(["exec.command", "exec.python", "file.read", "file.write", "file.list"]),
        command: z.string().optional(),
        script: z.string().optional(),
        filePath: z.string().optional(),
        content: z.string().optional(),
        purpose: z.string().default("task execution"),
      })
      .safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });

    if (parsed.data.operation === "exec.command") {
      const analysis = analyzeCommandRisk(parsed.data.command ?? "");
      if (analysis.requiresHumanApproval && task.classification !== "restricted") {
        return res.status(403).json({ error: "destructive_command_requires_human_approval", reason: analysis.reason });
      }
    }

    const grant = buildGrant({
      user: req.user!,
      taskId: task.id,
      agent: "engineering",
      tool: parsed.data.operation,
      operation: parsed.data.operation,
      purpose: parsed.data.purpose,
      classification: task.classification,
      budgetTokens: 500,
      budgetBytes: 50_000,
      reservationTokens: 50,
      reservationBytes: 1024,
      capability: parsed.data.operation,
      env,
    });
    grant.inputDigest = sha256(JSON.stringify(parsed.data));
    grant.normalizedParameters = { taskId: task.id, operation: parsed.data.operation };
    if (env.requireSignedGrants) {
      const signed = signGrant(grant as unknown as Record<string, unknown>, env.grantIssuer, env.grantPrivateKeyPem);
      grant.issuer = signed.issuer;
      grant.signature = signed.signature;
    }

    const decision = await governanceService(db, env).authorize(grant);
    if (!decision.allowed || !decision.capabilityLease) {
      return res.status(decision.status === "STOP" ? 423 : 403).json({ error: decision.reason });
    }

    if (parsed.data.operation === "exec.command") {
      const result = await runGovernedCommand({
        db, env, user: req.user!, taskId: task.id, command: parsed.data.command ?? "echo ok",
        actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease,
      });
      return res.json(result);
    }
    if (parsed.data.operation === "exec.python") {
      const result = await runGovernedPython({
        db, env, user: req.user!, taskId: task.id, script: parsed.data.script ?? "print('ok')",
        actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease,
      });
      return res.json(result);
    }
    if (parsed.data.operation === "file.read") {
      const result = await runGovernedFileRead({
        db, env, user: req.user!, taskId: task.id, filePath: parsed.data.filePath ?? "README.md",
        actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease,
      });
      return res.json(result);
    }
    if (parsed.data.operation === "file.write") {
      const result = await runGovernedFileWrite({
        db, env, user: req.user!, taskId: task.id, filePath: parsed.data.filePath ?? "output.txt", content: parsed.data.content ?? "",
        actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease,
      });
      return res.json(result);
    }
    if (parsed.data.operation === "file.list") {
      const result = await runGovernedFileList({
        db, env, user: req.user!, taskId: task.id, dirPath: parsed.data.filePath ?? ".",
        actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease,
      });
      return res.json(result);
    }
    return res.status(400).json({ error: "unsupported_operation" });
  }));

  app.post("/api/tasks/:taskId/browse", auth(), asyncRoute(async (req, res) => {
    const taskId = Number(req.params.taskId);
    if (!Number.isInteger(taskId)) return res.status(400).json({ error: "invalid_task_id" });
    const task = await repo.getTaskForUser(db, taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });

    const parsed = z
      .object({
        url: z.string().url(),
        purpose: z.string().default("web research"),
      })
      .safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });

    const grant = buildGrant({
      user: req.user!,
      taskId: task.id,
      agent: "research",
      tool: "browser.fetch",
      operation: "browser.fetch",
      purpose: parsed.data.purpose,
      classification: task.classification,
      budgetTokens: 500,
      budgetBytes: 100_000,
      reservationTokens: 50,
      reservationBytes: 1024,
      capability: "browser.fetch",
      env,
    });
    grant.inputDigest = sha256(parsed.data.url);
    grant.normalizedParameters = { taskId: task.id, url: parsed.data.url };
    if (env.requireSignedGrants) {
      const signed = signGrant(grant as unknown as Record<string, unknown>, env.grantIssuer, env.grantPrivateKeyPem);
      grant.issuer = signed.issuer;
      grant.signature = signed.signature;
    }

    const decision = await governanceService(db, env).authorize(grant);
    if (!decision.allowed || !decision.capabilityLease) {
      return res.status(decision.status === "STOP" ? 423 : 403).json({ error: decision.reason });
    }

    const result = await runGovernedBrowse({
      db, env, user: req.user!, taskId: task.id, url: parsed.data.url,
      actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease,
    });
    return res.json(result);
  }));

  /* ------------------------------------------------ world-class tools */

  app.post("/api/tasks/:taskId/visual-browse", auth(), asyncRoute(async (req, res) => {
    const taskId = Number(req.params.taskId);
    if (!Number.isInteger(taskId)) return res.status(400).json({ error: "invalid_task_id" });
    const task = await repo.getTaskForUser(db, taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });

    const parsed = z.object({
      url: z.string().url(),
      action: z.enum(["inspect", "click", "type", "screenshot"]).default("inspect"),
      selector: z.string().optional(),
      text: z.string().optional(),
      includeScreenshot: z.boolean().default(true),
    }).safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });

    const grant = buildGrant({
      user: req.user!,
      taskId: task.id,
      agent: "engineering",
      tool: "browser.visual",
      operation: `browser.${parsed.data.action}`,
      purpose: "visual inspection",
      classification: task.classification,
      budgetTokens: 500,
      budgetBytes: 100_000,
      reservationTokens: 50,
      reservationBytes: 1024,
      capability: "browser.visual",
      env,
    });
    grant.inputDigest = sha256(parsed.data.url);
    grant.normalizedParameters = { taskId: task.id, url: parsed.data.url, action: parsed.data.action };
    grant.providerParameters = { endpoint: parsed.data.url };
    if (env.requireSignedGrants) {
      const signed = signGrant(grant as unknown as Record<string, unknown>, env.grantIssuer, env.grantPrivateKeyPem);
      grant.issuer = signed.issuer;
      grant.signature = signed.signature;
    }

    const decision = await governanceService(db, env).authorize(grant);
    if (!decision.allowed || !decision.capabilityLease) {
      return res.status(decision.status === "STOP" ? 423 : 403).json({ error: decision.reason });
    }

    if (parsed.data.action === "inspect") {
      const result = await runGovernedVisualInspect({
        db,
        env,
        user: req.user!,
        taskId: task.id,
        url: parsed.data.url,
        includeScreenshot: parsed.data.includeScreenshot,
        actionDigest: decision.actionDigest,
        capabilityLease: decision.capabilityLease,
      });
      return res.json(result);
    } else {
      const result = await runGovernedBrowserAction({
        db,
        env,
        user: req.user!,
        taskId: task.id,
        url: parsed.data.url,
        action: parsed.data.action as "click" | "type" | "screenshot",
        selector: parsed.data.selector,
        text: parsed.data.text,
        actionDigest: decision.actionDigest,
        capabilityLease: decision.capabilityLease,
      });
      return res.json(result);
    }
  }));

  app.post("/api/tasks/:taskId/git", auth(), asyncRoute(async (req, res) => {
    const taskId = Number(req.params.taskId);
    if (!Number.isInteger(taskId)) return res.status(400).json({ error: "invalid_task_id" });
    const task = await repo.getTaskForUser(db, taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });

    const parsed = z.object({
      operation: z.enum(["status", "diff", "commit", "pr"]),
      message: z.string().optional(),
      title: z.string().optional(),
      body: z.string().optional(),
      sourceBranch: z.string().default("feature"),
    }).safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });

    const capability = parsed.data.operation === "pr" ? "github.pr" : `git.${parsed.data.operation}`;
    const grant = buildGrant({
      user: req.user!,
      taskId: task.id,
      agent: "engineering",
      tool: capability,
      operation: capability,
      purpose: "git repository workflow",
      classification: task.classification,
      budgetTokens: 500,
      budgetBytes: 100_000,
      reservationTokens: 50,
      reservationBytes: 1024,
      capability,
      env,
    });
    grant.inputDigest = sha256(JSON.stringify(parsed.data));
    grant.normalizedParameters = { taskId: task.id, ...parsed.data };
    if (env.requireSignedGrants) {
      const signed = signGrant(grant as unknown as Record<string, unknown>, env.grantIssuer, env.grantPrivateKeyPem);
      grant.issuer = signed.issuer;
      grant.signature = signed.signature;
    }

    const decision = await governanceService(db, env).authorize(grant);
    if (!decision.allowed || !decision.capabilityLease) {
      return res.status(decision.status === "STOP" ? 423 : 403).json({ error: decision.reason });
    }

    if (parsed.data.operation === "status") {
      return res.json(await runGovernedGitStatus({ db, env, user: req.user!, taskId: task.id, actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease }));
    } else if (parsed.data.operation === "diff") {
      return res.json(await runGovernedGitDiff({ db, env, user: req.user!, taskId: task.id, actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease }));
    } else if (parsed.data.operation === "commit") {
      return res.json(await runGovernedGitCommit({ db, env, user: req.user!, taskId: task.id, message: parsed.data.message || "update", actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease }));
    } else {
      return res.json(await runGovernedGitHubCreatePR({ db, env, user: req.user!, taskId: task.id, title: parsed.data.title || "Feature PR", body: parsed.data.body || "", sourceBranch: parsed.data.sourceBranch, actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease }));
    }
  }));

  app.post("/api/tasks/:taskId/memory", auth(), asyncRoute(async (req, res) => {
    const taskId = Number(req.params.taskId);
    if (!Number.isInteger(taskId)) return res.status(400).json({ error: "invalid_task_id" });
    const task = await repo.getTaskForUser(db, taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });

    const parsed = z.object({
      operation: z.enum(["store", "query"]),
      content: z.string().optional(),
      query: z.string().optional(),
      limit: z.number().int().positive().optional(),
    }).safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });

    const capability = parsed.data.operation === "store" ? "memory.store" : "memory.query";
    const grant = buildGrant({
      user: req.user!,
      taskId: task.id,
      agent: "engineering",
      tool: capability,
      operation: capability,
      purpose: "semantic vector memory",
      classification: task.classification,
      budgetTokens: 500,
      budgetBytes: 100_000,
      reservationTokens: 50,
      reservationBytes: 1024,
      capability,
      env,
    });
    grant.inputDigest = sha256(parsed.data.content || parsed.data.query || "");
    grant.normalizedParameters = { taskId: task.id, ...parsed.data };
    if (env.requireSignedGrants) {
      const signed = signGrant(grant as unknown as Record<string, unknown>, env.grantIssuer, env.grantPrivateKeyPem);
      grant.issuer = signed.issuer;
      grant.signature = signed.signature;
    }

    const decision = await governanceService(db, env).authorize(grant);
    if (!decision.allowed || !decision.capabilityLease) {
      return res.status(decision.status === "STOP" ? 423 : 403).json({ error: decision.reason });
    }

    if (parsed.data.operation === "store") {
      return res.json(await runGovernedMemoryStore({ db, env, user: req.user!, taskId: task.id, content: parsed.data.content || "", actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease }));
    } else {
      return res.json(await runGovernedMemoryQuery({ db, env, user: req.user!, taskId: task.id, query: parsed.data.query || "", limit: parsed.data.limit, actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease }));
    }
  }));

  app.post("/api/tasks/:taskId/code", auth(), asyncRoute(async (req, res) => {
    const taskId = Number(req.params.taskId);
    if (!Number.isInteger(taskId)) return res.status(400).json({ error: "invalid_task_id" });
    const task = await repo.getTaskForUser(db, taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });

    const parsed = z.object({
      operation: z.enum(["symbols", "definition"]),
      filePath: z.string().optional(),
      symbolName: z.string().optional(),
    }).safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });

    const capability = parsed.data.operation === "symbols" ? "code.symbols" : "code.definition";
    const grant = buildGrant({
      user: req.user!,
      taskId: task.id,
      agent: "engineering",
      tool: capability,
      operation: capability,
      purpose: "code intelligence navigation",
      classification: task.classification,
      budgetTokens: 500,
      budgetBytes: 100_000,
      reservationTokens: 50,
      reservationBytes: 1024,
      capability,
      env,
    });
    grant.inputDigest = sha256(parsed.data.symbolName || parsed.data.filePath || "");
    grant.normalizedParameters = { taskId: task.id, ...parsed.data };
    if (env.requireSignedGrants) {
      const signed = signGrant(grant as unknown as Record<string, unknown>, env.grantIssuer, env.grantPrivateKeyPem);
      grant.issuer = signed.issuer;
      grant.signature = signed.signature;
    }

    const decision = await governanceService(db, env).authorize(grant);
    if (!decision.allowed || !decision.capabilityLease) {
      return res.status(decision.status === "STOP" ? 423 : 403).json({ error: decision.reason });
    }

    if (parsed.data.operation === "symbols") {
      return res.json(await runGovernedFindSymbols({ db, env, user: req.user!, taskId: task.id, filePath: parsed.data.filePath, actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease }));
    } else {
      return res.json(await runGovernedFindDefinition({ db, env, user: req.user!, taskId: task.id, symbolName: parsed.data.symbolName || "", actionDigest: decision.actionDigest, capabilityLease: decision.capabilityLease }));
    }
  }));

  /* -------------------------------------------------------------- audit */

  app.get("/api/audit", auth(), adminOnly(), asyncRoute(async (req, res) => {
    const taskId = req.query.taskId ? Number(req.query.taskId) : undefined;
    if (taskId) {
      const task = await repo.getTaskForUser(db, taskId, req.user!.workspaceId);
      if (!task) return res.status(404).json({ error: "task_not_found" });
    }
    return res.json({ events: await listAudit(db, taskId, 300) });
  }));

  app.get("/api/audit/bundle/:taskId", auth(), adminOnly(), asyncRoute(async (req, res) => {
    const taskId = Number(req.params.taskId);
    if (!Number.isInteger(taskId)) return res.status(400).json({ error: "invalid_task_id" });
    const task = await repo.getTaskForUser(db, taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });
    const bundle = await exportAuditProofBundle(db, taskId);
    return res.json(bundle);
  }));

  app.post("/api/audit/verify-proof", auth(), asyncRoute(async (req, res) => {
    const parsed = z
      .object({
        targetHash: z.string(),
        rootHash: z.string(),
        index: z.number().int().min(0),
        totalLeaves: z.number().int().positive(),
        path: z.array(z.object({ position: z.enum(["left", "right"]), hash: z.string() })),
      })
      .safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_proof_format" });
    const valid = verifyMerkleProof(parsed.data);
    return res.json({ valid, targetHash: parsed.data.targetHash, rootHash: parsed.data.rootHash });
  }));

  app.get("/api/audit/verify", auth(), adminOnly(), asyncRoute(async (_req, res) => {
    res.json(await verifyAuditChain(db));
  }));

  /* ----------------------------------------------------------- controls */

  app.get("/api/controls/interlock", auth(), asyncRoute(async (_req, res) => {
    res.json(await repo.getInterlock(db));
  }));

  app.post("/api/controls/interlock", auth(), adminOnly(), asyncRoute(async (req, res) => {
    const parsed = z.object({ killSwitch: z.boolean().optional(), circuitOpen: z.boolean().optional() }).safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });
    const interlock = await repo.setInterlock(db, parsed.data, req.user!.id);
    await appendAudit(db, { actorUserId: req.user!.id, eventType: "safety_control_changed", decision: interlock.killSwitch || interlock.circuitOpen ? "STOP" : "ALLOW", reason: "interlock_updated", payload: interlock });
    return res.json(interlock);
  }));

  /* ----------------------------------------------------------- quorum & invariants */

  const quorumEngine = new MultiAgentQuorumEngine(0.66);
  const invariantEngine = new TrajectoryInvariantEngine();

  app.post("/api/governance/quorum/propose", auth(), asyncRoute(async (req, res) => {
    const parsed = z.object({
      taskId: z.number().int().positive(),
      tool: z.string().min(1),
      operation: z.string().min(1),
      parameters: z.record(z.unknown()),
      justification: z.string().min(1),
      isDestructive: z.boolean().optional(),
    }).safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });

    const task = await repo.getTaskForUser(db, parsed.data.taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });

    const proposal = quorumEngine.createProposal({
      taskId: task.id,
      actorUserId: req.user!.id,
      tool: parsed.data.tool,
      operation: parsed.data.operation,
      parameters: parsed.data.parameters,
      justification: parsed.data.justification,
      isDestructive: parsed.data.isDestructive,
    });

    quorumEngine.submitVote({
      proposalId: proposal.proposalId,
      role: "coder_proposer",
      agentId: `proposer-user-${req.user!.id}`,
      approve: true,
      reason: "Action proposed and validated by initiator.",
      timestamp: Date.now(),
    });

    quorumEngine.auditSecurity(proposal.proposalId);
    quorumEngine.adjudicateChiefJustice(proposal.proposalId);
    const result = quorumEngine.adjudicate(proposal.proposalId);

    await appendAudit(db, {
      taskId: task.id,
      actorUserId: req.user!.id,
      eventType: "quorum_consensus",
      decision: result.status === "APPROVED" ? "ALLOW" : "DENY",
      reason: `quorum_${result.status.toLowerCase()}`,
      payload: { proposalId: proposal.proposalId, status: result.status, consensusRatio: result.consensusRatio, consensusDigest: result.consensusDigest },
    });

    return res.json({ proposal, result });
  }));

  app.get("/api/governance/quorum/:proposalId", auth(), asyncRoute(async (req, res) => {
    const proposal = quorumEngine.getProposal(req.params.proposalId);
    if (!proposal) return res.status(404).json({ error: "proposal_not_found" });
    const result = quorumEngine.getResult(req.params.proposalId);
    return res.json({ proposal, result });
  }));

  app.post("/api/governance/invariants/check", auth(), asyncRoute(async (req, res) => {
    const parsed = z.object({
      taskId: z.number().int().positive(),
      tool: z.string().min(1),
      parameters: z.record(z.unknown()),
    }).safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input" });

    const task = await repo.getTaskForUser(db, parsed.data.taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });

    const check = invariantEngine.checkInvariants({
      taskId: task.id,
      tool: parsed.data.tool,
      parameters: parsed.data.parameters,
    });

    return res.json(check);
  }));

  /* ----------------------------------------------------------- skills catalog & execution */

  const skillRegistry = createDefaultSkillRegistry();

  app.get("/api/skills", auth(), asyncRoute(async (req, res) => {
    const category = typeof req.query.category === "string" ? req.query.category : undefined;
    const specialist = typeof req.query.specialist === "string" ? req.query.specialist : undefined;
    const search = typeof req.query.search === "string" ? req.query.search : undefined;

    let skills = skillRegistry.listSkills();
    if (category) skills = skills.filter(s => s.category === category);
    if (specialist) skills = skills.filter(s => s.specialist === specialist);
    if (search) skills = skillRegistry.searchSkills(search);

    return res.json({ total: skills.length, skills });
  }));

  app.get("/api/skills/:skillId", auth(), asyncRoute(async (req, res) => {
    const skill = skillRegistry.getSkill(req.params.skillId);
    if (!skill) return res.status(404).json({ error: "skill_not_found" });
    return res.json({ metadata: skill.metadata });
  }));

  app.post("/api/skills/:skillId/execute", auth(), asyncRoute(async (req, res) => {
    const skill = skillRegistry.getSkill(req.params.skillId);
    if (!skill) return res.status(404).json({ error: "skill_not_found" });

    const parsed = z.object({
      taskId: z.number().int().positive(),
      parameters: z.record(z.unknown()),
      cognitiveStage: z.enum(["observe", "understand", "reason", "plan", "act", "verify", "critique", "learn"]).default("act"),
    }).safeParse(req.body);
    if (!parsed.success) return res.status(400).json({ error: "invalid_input", detail: parsed.error.message });

    const task = await repo.getTaskForUser(db, parsed.data.taskId, req.user!.workspaceId);
    if (!task) return res.status(404).json({ error: "task_not_found" });

    const capability = skill.metadata.requiredCapability;
    const grant = buildGrant({
      user: req.user!,
      taskId: task.id,
      agent: skill.metadata.specialist,
      tool: capability,
      operation: `skill:${skill.metadata.id}`,
      purpose: `Executing skill ${skill.metadata.name}`,
      classification: task.classification,
      budgetTokens: skill.metadata.costTokensEstimate,
      budgetBytes: 100_000,
      capability,
      env,
    });
    grant.inputDigest = sha256(canonicalize(parsed.data.parameters));
    grant.normalizedParameters = { taskId: task.id, skillId: skill.metadata.id, ...parsed.data.parameters };
    if (env.requireSignedGrants) {
      const signed = signGrant(grant as unknown as Record<string, unknown>, env.grantIssuer, env.grantPrivateKeyPem);
      grant.issuer = signed.issuer;
      grant.signature = signed.signature;
    }

    const decision = await governanceService(db, env).authorize(grant);
    if (!decision.allowed || !decision.capabilityLease) {
      return res.status(decision.status === "STOP" ? 423 : 403).json({ error: decision.reason });
    }

    const result = await skillRegistry.executeSkill(
      skill.metadata.id,
      {
        taskId: task.id,
        actorUserId: req.user!.id,
        actionDigest: decision.actionDigest,
        capabilityLease: decision.capabilityLease,
        parameters: parsed.data.parameters,
        cognitiveStage: parsed.data.cognitiveStage,
      },
      env.grantPublicKeyPem
    );

    await appendAudit(db, {
      taskId: task.id,
      actorUserId: req.user!.id,
      eventType: "skill_executed",
      decision: result.success ? "ALLOW" : "DENY",
      reason: result.success ? "skill_completed" : "postcondition_failed",
      payload: {
        skillId: skill.metadata.id,
        stage: result.stage,
        evidenceHash: result.evidenceHash,
        durationMs: result.executionDurationMs,
      },
    });

    return res.json(result);
  }));

  /* ------------------------------------------------------ static client */

  const publicDir = path.resolve(process.cwd(), "dist/public");
  if (fs.existsSync(publicDir)) {
    app.use(express.static(publicDir, { maxAge: env.isProduction ? "1h" : 0, index: false }));
    app.get(/^(?!\/api\/).*/, (_req, res) => res.sendFile(path.join(publicDir, "index.html")));
  }

  app.use("/api", (_req, res) => res.status(404).json({ error: "not_found" }));

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  app.use((error: Error, _req: Request, res: Response, _next: NextFunction) => {
    console.error(JSON.stringify({ level: "error", event: "unhandled_error", message: error.message, stack: error.stack?.split("\n").slice(0, 4) }));
    res.status(500).json({ error: "internal_error" });
  });

  return app;
}
