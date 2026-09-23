import { describe, expect, it } from "vitest";
import { assertEgressUrl, assertHttpsUrl, isPrivateOrLocalHost } from "../src/server/security.js";

describe("Step 8 egress and interlock boundary", () => {
  it("requires HTTPS and rejects URL credentials", () => {
    expect(() => assertHttpsUrl("http://api.example.com/x")).toThrow("https_required");
    expect(() => assertHttpsUrl("https://user:pass@api.example.com/x")).toThrow("url_credentials_forbidden");
  });

  it("blocks local, private, metadata, and unapproved destinations", () => {
    for (const host of ["localhost", "127.0.0.1", "10.0.0.1", "169.254.169.254", "metadata.google.internal", "service.internal"]) {
      expect(isPrivateOrLocalHost(host)).toBe(true);
      expect(() => assertEgressUrl(`https://${host}/`, [host])).toThrow("private_destination_blocked");
    }
    expect(() => assertEgressUrl("https://not-approved.example/x", ["approved.example"])).toThrow("egress_destination_not_allowlisted");
  });

  it("supports exact and controlled subdomain allowlists only", () => {
    expect(assertEgressUrl("https://api.approved.example/v1", ["*.approved.example"]).hostname).toBe("api.approved.example");
    expect(() => assertEgressUrl("https://approved.example.evil.test/", ["*.approved.example"])).toThrow("egress_destination_not_allowlisted");
  });
});
