import { describe, expect, it } from "vitest";

type RecordValue = { generation: number; response: unknown };

class ReferenceProviderContract {
  private readonly currentGeneration = new Map<string, number>();
  private readonly idempotent = new Map<string, RecordValue>();
  submit(input: { resource: string; generation: number; idempotencyKey: string; response: unknown }) {
    const current = this.currentGeneration.get(input.resource) ?? 0;
    if (input.generation < current) return { status: 412, effect: false };
    const previous = this.idempotent.get(input.idempotencyKey);
    if (previous) return { status: 200, effect: false, response: previous.response };
    this.currentGeneration.set(input.resource, input.generation);
    this.idempotent.set(input.idempotencyKey, { generation: input.generation, response: input.response });
    return { status: 200, effect: true, response: input.response };
  }
}

describe("Phase 4 provider contract", () => {
  it("converges duplicate requests by idempotency key", () => {
    const p = new ReferenceProviderContract();
    const a = p.submit({ resource: "video:1", generation: 4, idempotencyKey: "k", response: { id: "job-1" } });
    const b = p.submit({ resource: "video:1", generation: 4, idempotencyKey: "k", response: { id: "job-2" } });
    expect(a.effect).toBe(true); expect(b.effect).toBe(false); expect(b.response).toEqual({ id: "job-1" });
  });
  it("rejects a stale fencing generation without effect", () => {
    const p = new ReferenceProviderContract();
    expect(p.submit({ resource: "video:2", generation: 8, idempotencyKey: "k8", response: { id: "job-8" } }).effect).toBe(true);
    const stale = p.submit({ resource: "video:2", generation: 7, idempotencyKey: "k7", response: { id: "job-7" } });
    expect(stale.status).toBe(412); expect(stale.effect).toBe(false);
  });
});
