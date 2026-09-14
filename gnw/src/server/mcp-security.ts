import { createHash, randomBytes } from "node:crypto";

export type McpResourceMetadata = {
  resource: string;
  authorization_servers: string[];
  scopes_supported?: string[];
};

export function canonicalResourceUri(raw: string): string {
  const url = new URL(raw);
  if (url.protocol !== "https:") throw new Error("mcp_https_required");
  if (url.username || url.password || url.hash) throw new Error("mcp_resource_uri_invalid");
  url.search = "";
  return url.toString();
}

export function assertMcpResourceAudience(tokenAudience: string | string[] | undefined, expectedResource: string): boolean {
  if (!tokenAudience) return false;
  const audience = Array.isArray(tokenAudience) ? tokenAudience : [tokenAudience];
  const expected = canonicalResourceUri(expectedResource);
  return audience.some(value => canonicalResourceUri(value) === expected);
}

export function assertMcpScopes(granted: string[], required: string[]): boolean {
  const set = new Set(granted);
  return required.every(scope => set.has(scope));
}

export function validateRedirectUri(candidate: string, registered: string[]): boolean {
  const parsed = new URL(candidate);
  if (parsed.protocol !== "https:" || parsed.hash) return false;
  return registered.some(item => item === candidate);
}

export function createPkceChallenge(verifier = randomBytes(32).toString("base64url")) {
  if (verifier.length < 43 || verifier.length > 128) throw new Error("pkce_verifier_length");
  return { verifier, challenge: createHash("sha256").update(verifier).digest("base64url"), method: "S256" as const };
}

export function validateProtectedResourceMetadata(metadata: McpResourceMetadata, expectedResource: string): boolean {
  if (canonicalResourceUri(metadata.resource) !== canonicalResourceUri(expectedResource)) return false;
  return metadata.authorization_servers.length > 0 && metadata.authorization_servers.every(server => new URL(server).protocol === "https:");
}
