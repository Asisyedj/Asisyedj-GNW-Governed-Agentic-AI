import { describe, expect, it } from "vitest";
import { loadEnv } from "../src/server/env.js";
import { assertEgressUrl } from "../src/server/security.js";
import { buildS3RequestUrl } from "../src/server/storage.js";

describe("S3 endpoint addressing", () => {
  it("uses Railway virtual-hosted URLs and encodes object-key segments", () => {
    const env = loadEnv({
      NODE_ENV: "test",
      S3_ENDPOINT: "https://t3.storageapi.dev",
      S3_URL_STYLE: "virtual",
    });
    const url = buildS3RequestUrl(env, "gnw-artifacts-ab123", "artifacts/report one.json");
    expect(url.origin).toBe("https://gnw-artifacts-ab123.t3.storageapi.dev");
    expect(url.pathname).toBe("/artifacts/report%20one.json");
    expect(() => assertEgressUrl(url.toString(), ["*.t3.storageapi.dev"])).not.toThrow();
    expect(() => assertEgressUrl(url.toString(), ["t3.storageapi.dev"])).toThrow("egress_destination_not_allowlisted");
  });

  it("preserves the existing path-style addressing contract", () => {
    const env = loadEnv({
      NODE_ENV: "test",
      S3_ENDPOINT: "https://s3.example.test",
      S3_URL_STYLE: "path",
    });
    const url = buildS3RequestUrl(env, "gnw-bucket", "artifacts/a.json");
    expect(url.origin).toBe("https://s3.example.test");
    expect(url.pathname).toBe("/gnw-bucket/artifacts/a.json");
    expect(() => assertEgressUrl(url.toString(), ["s3.example.test"])).not.toThrow();
  });
});
