import fs from "node:fs/promises";
import { createHmac } from "node:crypto";
import path from "node:path";
import { ENV, type Env } from "./env.js";
import { assertEgressUrl, governedFetch, sha256 } from "./security.js";

export type StoredObject = { key: string; url: string | null; byteSize: number; driver: "local" | "s3" };

function safeKey(key: string) {
  if (!key || key.length > 512 || key.includes("\0")) throw new Error("invalid_storage_key");
  const normalized = key.replaceAll("\\", "/");
  if (normalized.startsWith("/") || normalized.split("/").some(part => part === ".." || part === ".")) throw new Error("storage_path_traversal");
  return normalized;
}

/**
 * Artifact bytes are always addressed by an external storage reference. The
 * application database stores the key, digest and size — never the payload.
 */
export async function storagePut(key: string, body: string | Buffer, contentType: string, env: Env = ENV): Promise<StoredObject> {
  const safe = safeKey(key);
  const buffer = Buffer.isBuffer(body) ? body : Buffer.from(body, "utf8");
  if (buffer.byteLength > env.maxArtifactBytes) throw new Error("artifact_too_large");
  if (env.storageDriver === "s3") return putToS3(safe, buffer, contentType, env);
  const root = path.resolve(env.artifactDir);
  const target = path.resolve(root, safe);
  if (target !== root && !target.startsWith(`${root}${path.sep}`)) throw new Error("storage_path_escape");
  await fs.mkdir(path.dirname(target), { recursive: true });
  // Refuse symlinked path components to reduce link/junction escape risk.
  // The final open is still subject to the host filesystem semantics, so
  // production deployments should place ARTIFACT_DIR on a dedicated volume.
  const relative = path.relative(root, target);
  let cursor = root;
  for (const part of relative.split(path.sep).filter(Boolean)) {
    cursor = path.join(cursor, part);
    try {
      const entry = await fs.lstat(cursor);
      if (entry.isSymbolicLink()) throw new Error("storage_symlink_escape");
    } catch (error) {
      if (error instanceof Error && error.message === "storage_symlink_escape") throw error;
      // A missing final component is expected immediately before write.
      if (cursor !== target) throw error;
    }
  }
  await fs.writeFile(target, buffer, { flag: "wx" }).catch(async error => {
    if (error && typeof error === "object" && "code" in error && error.code === "EEXIST") {
      await fs.writeFile(target, buffer);
      return;
    }
    throw error;
  });
  return { key: safe, url: null, byteSize: buffer.byteLength, driver: "local" };
}

export async function storageGet(key: string, env: Env = ENV): Promise<Buffer | null> {
  const safe = safeKey(key);
  if (env.storageDriver === "s3") return getFromS3(safe, env);
  try {
    const root = path.resolve(env.artifactDir);
    const target = path.resolve(root, safe);
    if (target !== root && !target.startsWith(`${root}${path.sep}`)) return null;
    const stat = await fs.lstat(target);
    if (stat.isSymbolicLink() || !stat.isFile() || stat.size > env.maxArtifactBytes) return null;
    return await fs.readFile(target);
  } catch {
    return null;
  }
}

function hmac(key: Buffer | string, data: string): Buffer {
  return createHmac("sha256", key).update(data).digest();
}

function awsSigningKey(secret: string, date: string, region: string, service = "s3") {
  const kDate = hmac(`AWS4${secret}`, date);
  const kRegion = hmac(kDate, region);
  const kService = hmac(kRegion, service);
  return hmac(kService, "aws4_request");
}

function awsUriPath(bucket: string, key: string) {
  return `/${encodeURIComponent(bucket).replace(/%2F/g, "/")}/${key.split("/").map(encodeURIComponent).join("/")}`;
}

function awsHost(env: Env) {
  if (env.s3.endpoint) return new URL(env.s3.endpoint).host;
  return `s3.${env.s3.region || "us-east-1"}.amazonaws.com`;
}

function awsEndpoint(env: Env, bucket: string, key: string) {
  const base = env.s3.endpoint ? new URL(env.s3.endpoint) : new URL(`https://${awsHost(env)}`);
  base.pathname = awsUriPath(bucket, key);
  base.search = "";
  return base;
}

async function signedS3Request(method: "GET" | "PUT", key: string, body: Buffer | undefined, contentType: string | undefined, env: Env) {
  if (!env.s3.bucket || !env.s3.region || !env.s3.accessKeyId || !env.s3.secretAccessKey) throw new Error("s3_configuration_incomplete");
  const url = awsEndpoint(env, env.s3.bucket, key);
  assertEgressUrl(url.toString(), env.allowedEgressHosts);

  const now = new Date();
  const amzDate = now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  const shortDate = amzDate.slice(0, 8);
  const payloadHash = sha256(body ?? Buffer.alloc(0));
  const canonicalHeaders = `host:${url.host}\nx-amz-content-sha256:${payloadHash}\nx-amz-date:${amzDate}\n`;
  const signedHeaders = "host;x-amz-content-sha256;x-amz-date";
  const canonicalRequest = `${method}\n${url.pathname}\n\n${canonicalHeaders}\n${signedHeaders}\n${payloadHash}`;
  const credentialScope = `${shortDate}/${env.s3.region}/s3/aws4_request`;
  const stringToSign = `AWS4-HMAC-SHA256\n${amzDate}\n${credentialScope}\n${sha256(canonicalRequest)}`;
  const signature = hmac(awsSigningKey(env.s3.secretAccessKey, shortDate, env.s3.region), stringToSign).toString("hex");
  const authorization = `AWS4-HMAC-SHA256 Credential=${env.s3.accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

  const response = await governedFetch(url.toString(), {
    method,
    redirect: "manual",
    headers: {
      host: url.host,
      "x-amz-content-sha256": payloadHash,
      "x-amz-date": amzDate,
      authorization,
      ...(contentType ? { "content-type": contentType } : {}),
    },
    body: method === "PUT" ? body : undefined,
    __allowedHosts: env.allowedEgressHosts,
  } as RequestInit & { __allowedHosts: readonly string[] }, env.maxArtifactBytes);
  if (!response.ok) throw new Error(`s3_request_failed:${response.status}`);
  return response;
}

async function putToS3(key: string, buffer: Buffer, contentType: string, env: Env): Promise<StoredObject> {
  await signedS3Request("PUT", key, buffer, contentType, env);
  const url = env.s3.publicBaseUrl ? `${env.s3.publicBaseUrl.replace(/\/$/, "")}/${key}` : null;
  return { key, url, byteSize: buffer.byteLength, driver: "s3" };
}

async function getFromS3(key: string, env: Env): Promise<Buffer | null> {
  try {
    const response = await signedS3Request("GET", key, undefined, undefined, env);
    const contentLength = Number(response.headers.get("content-length") ?? "0");
    if (contentLength > env.maxArtifactBytes) return null;
    const data = Buffer.from(await response.arrayBuffer());
    return data.byteLength <= env.maxArtifactBytes ? data : null;
  } catch {
    return null;
  }
}
