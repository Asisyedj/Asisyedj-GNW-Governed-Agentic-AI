import http from "node:http";
import { TaskSandbox } from "../server/sandbox/index.js";
import { assertExecutorAuthorization } from "./auth.js";

const port = Number(process.env.EXECUTOR_PORT ?? 8790);
const token = process.env.EXECUTOR_SHARED_TOKEN ?? "";
const issuer = process.env.EXECUTOR_GRANT_ISSUER ?? "";
const publicKeyPem = process.env.EXECUTOR_GRANT_PUBLIC_KEY_PEM ?? "";
const base = process.env.EXECUTOR_ARTIFACT_DIR ?? "/data/artifacts";

function reply(res: http.ServerResponse, status: number, body: unknown) {
  const raw = JSON.stringify(body);
  res.writeHead(status, { "content-type": "application/json", "content-length": Buffer.byteLength(raw) });
  res.end(raw);
}

function body(req: http.IncomingMessage) {
  return new Promise<string>((resolve, reject) => {
    let n = 0;
    const chunks: Buffer[] = [];
    req.on("data", chunk => {
      const b = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      n += b.length;
      if (n > 262144) {
        req.destroy();
        reject(new Error("body_too_large"));
        return;
      }
      chunks.push(b);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString()));
    req.on("error", reject);
  });
}

http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/health") return reply(res, 200, { status: "ok", service: "gnw-executor" });
  if (req.method !== "POST" || req.url !== "/v1/execute") return reply(res, 404, { error: "not_found" });
  if (!token || req.headers.authorization !== `Bearer ${token}`) return reply(res, 401, { error: "executor_auth_required" });
  if (!issuer || !publicKeyPem) return reply(res, 503, { error: "executor_trust_not_configured" });

  try {
    const x = JSON.parse(await body(req));
    if (!Number.isInteger(x.taskId) || x.taskId < 1 || typeof x.command !== "string" || !x.command.length || x.command.length > 16384) return reply(res, 400, { error: "invalid_execution_request" });
    assertExecutorAuthorization(x.authorization, x.taskId, issuer, publicKeyPem);
    const s = new TaskSandbox(x.taskId, `${base}/sandboxes`);
    await s.init();
    for (const f of Array.isArray(x.files) ? x.files : []) {
      if (!f || typeof f.path !== "string" || typeof f.content !== "string" || f.path.includes("..") || f.path.startsWith("/")) return reply(res, 400, { error: "invalid_executor_file" });
      await s.writeFile(f.path, f.content);
    }
    const r = await s.execute(x.command, Array.isArray(x.args) ? x.args : [], {
      timeoutMs: Math.min(Math.max(x.timeoutMs ?? 45000, 100), 120000),
      maxOutputBytes: Math.min(Math.max(x.maxOutputBytes ?? 1000000, 1024), 10000000),
    });
    return reply(res, 200, r);
  } catch (e) {
    const message = e instanceof Error ? e.message : "executor_failed";
    const status = message === "executor_trust_not_configured" ? 503 : message.startsWith("executor_") ? 403 : 400;
    return reply(res, status, { error: message });
  }
}).listen(port, "0.0.0.0", () => console.log(`GNW executor listening on ${port}`));
