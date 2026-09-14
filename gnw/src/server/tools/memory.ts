import type { Db } from "../db/index.js";
import type { Env } from "../env.js";
import type { SessionUser } from "../auth.js";
import type { CapabilityLease } from "../capability.js";
import { executeExternal } from "../execution.js";
import { sanitizePromptInput } from "../security/guard.js";

export type MemoryTier = "L1_working" | "L2_episodic" | "L3_semantic" | "L4_procedural";

export type VectorDocument = {
  id: string;
  tenantKey: string;
  taskId: number;
  content: string;
  tier?: MemoryTier;
  subjectKey?: string;
  invalidated?: boolean;
  supersededBy?: string;
  metadata?: Record<string, unknown>;
  vector: number[];
  timestamp: number;
};

export type QueryResultItem = {
  id: string;
  content: string;
  similarity: number;
  tier?: MemoryTier;
  subjectKey?: string;
  metadata?: Record<string, unknown>;
};

const vectorStore = new Map<string, VectorDocument>();

export function computeEmbedding(text: string, dimensions = 64): number[] {
  const clean = text.toLowerCase().replace(/[^a-z0-9\s]/g, " ");
  const tokens = clean.split(/\s+/).filter(Boolean);
  const vector = new Array(dimensions).fill(0);

  for (const token of tokens) {
    let hash = 0;
    for (let i = 0; i < token.length; i++) {
      hash = (hash << 5) - hash + token.charCodeAt(i);
      hash |= 0;
    }
    const bucket = Math.abs(hash) % dimensions;
    vector[bucket] += 1;
  }

  for (let i = 0; i < clean.length - 2; i++) {
    const trigram = clean.slice(i, i + 3);
    let hash = 0;
    for (let j = 0; j < 3; j++) {
      hash = (hash << 5) - hash + trigram.charCodeAt(j);
      hash |= 0;
    }
    const bucket = Math.abs(hash) % dimensions;
    vector[bucket] += 0.5;
  }

  let norm = 0;
  for (let i = 0; i < dimensions; i++) {
    norm += vector[i] * vector[i];
  }
  norm = Math.sqrt(norm);
  if (norm > 0) {
    for (let i = 0; i < dimensions; i++) {
      vector[i] /= norm;
    }
  }

  return vector;
}

export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0;
  let dotProduct = 0;
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
  }
  return Math.max(0, Math.min(1, dotProduct));
}

export async function runGovernedMemoryStore(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  content: string;
  tier?: MemoryTier;
  subjectKey?: string;
  metadata?: Record<string, unknown>;
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<{ id: string; stored: boolean; vectorDimensions: number; invalidatedOlderCount?: number }> {
  if (p.capabilityLease.tenant !== p.user.tenantKey) throw new Error("memory_tenant_binding");
  const cleanContent = sanitizePromptInput(p.content);

  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "memory_store",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "memory.store",
    effect: async () => {
      const id = `doc_${Math.random().toString(36).slice(2, 10)}`;
      const vector = computeEmbedding(cleanContent);
      const tier: MemoryTier = p.tier ?? "L3_semantic";
      const subjectKey = p.subjectKey ?? (typeof p.metadata?.subjectKey === "string" ? p.metadata.subjectKey : undefined);

      // AGM Belief Revision / Anti-Memory-Rot:
      // If a subjectKey is provided, invalidate older matching entries to prevent stale truth rot.
      let invalidatedOlderCount = 0;
      if (subjectKey) {
        for (const doc of vectorStore.values()) {
          if (doc.tenantKey === p.user.tenantKey && doc.subjectKey === subjectKey && !doc.invalidated) {
            doc.invalidated = true;
            doc.supersededBy = id;
            invalidatedOlderCount++;
          }
        }
      }

      vectorStore.set(id, {
        id,
        tenantKey: p.user.tenantKey,
        taskId: p.taskId,
        content: cleanContent,
        tier,
        subjectKey,
        invalidated: false,
        metadata: p.metadata,
        vector,
        timestamp: Date.now(),
      });

      return {
        id,
        stored: true,
        vectorDimensions: vector.length,
        invalidatedOlderCount,
      };
    },
  });
}

export async function runGovernedMemoryQuery(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  query: string;
  tier?: MemoryTier;
  includeInvalidated?: boolean;
  limit?: number;
  minSimilarity?: number;
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<{ query: string; results: QueryResultItem[]; totalScanned: number }> {
  if (p.capabilityLease.tenant !== p.user.tenantKey) throw new Error("memory_tenant_binding");
  const cleanQuery = sanitizePromptInput(p.query);

  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "memory_query",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "memory.query",
    effect: async () => {
      const queryVector = computeEmbedding(cleanQuery);
      const limit = Math.max(1, Math.min(20, p.limit ?? 5));
      const minSimilarity = p.minSimilarity ?? 0.1;
      const now = Date.now();

      const scored: QueryResultItem[] = [];

      for (const doc of vectorStore.values()) {
        if (doc.tenantKey !== p.user.tenantKey) continue;
        // Truth-maintenance filter: ignore invalidated / superseded stale beliefs by default
        if (doc.invalidated && !p.includeInvalidated) continue;
        if (p.tier && doc.tier !== p.tier) continue;

        const baseSimilarity = cosineSimilarity(queryVector, doc.vector);
        // Recency weighting (exponential temporal decay over 30 days)
        const daysOld = (now - doc.timestamp) / (1000 * 60 * 60 * 24);
        const freshnessMultiplier = Math.exp(-0.02 * daysOld); // gentle decay
        const finalScore = Math.max(0, Math.min(1, baseSimilarity * 0.85 + freshnessMultiplier * 0.15));

        if (finalScore >= minSimilarity) {
          scored.push({
            id: doc.id,
            content: doc.content,
            similarity: Math.round(finalScore * 1000) / 1000,
            tier: doc.tier,
            subjectKey: doc.subjectKey,
            metadata: doc.metadata,
          });
        }
      }

      scored.sort((a, b) => b.similarity - a.similarity);

      return {
        query: cleanQuery,
        results: scored.slice(0, limit),
        totalScanned: vectorStore.size,
      };
    },
  });
}
