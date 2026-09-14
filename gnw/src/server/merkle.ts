import { createHash, createPrivateKey, createPublicKey, sign as cryptoSign, verify as cryptoVerify } from "node:crypto";
import type { Db } from "./db/index.js";
import { GENESIS_HASH, listAuditComplete, verifyAuditChain, type AuditRow } from "./audit.js";
import { canonicalize } from "./security.js";

export function sha256(data: string): string { return createHash("sha256").update(data).digest("hex"); }
export function hashPair(left: string, right: string): string { return sha256(`GNW-MERKLE-NODE-V1|${left}|${right}`); }

export type MerkleProofStep = { position: "left" | "right"; hash: string };
export type MerkleProof = { targetHash: string; rootHash: string; index: number; totalLeaves: number; path: MerkleProofStep[] };
export type MerkleTree = { root: string; leaves: string[]; levels: string[][] };

export function buildMerkleTree(leafHashes: string[]): MerkleTree {
  if (leafHashes.length === 0) {
    const emptyRoot = sha256("GNW_EMPTY_MERKLE_TREE_V1");
    return { root: emptyRoot, leaves: [], levels: [[emptyRoot]] };
  }
  const levels: string[][] = [leafHashes.slice()];
  let current = leafHashes.slice();
  while (current.length > 1) {
    const next: string[] = [];
    for (let i = 0; i < current.length; i += 2) {
      const left = current[i];
      const right = i + 1 < current.length ? current[i + 1] : left;
      next.push(hashPair(left, right));
    }
    levels.push(next);
    current = next;
  }
  return { root: current[0], leaves: leafHashes, levels };
}

export function generateMerkleProof(tree: MerkleTree, index: number): MerkleProof {
  if (index < 0 || index >= tree.leaves.length) throw new Error("merkle_index_out_of_bounds");
  const path: MerkleProofStep[] = [];
  let currentIndex = index;
  for (let level = 0; level < tree.levels.length - 1; level++) {
    const currentLevel = tree.levels[level];
    const isRight = currentIndex % 2 === 1;
    const siblingIndex = isRight ? currentIndex - 1 : currentIndex + 1;
    path.push({ position: isRight ? "left" : "right", hash: siblingIndex < currentLevel.length ? currentLevel[siblingIndex] : currentLevel[currentIndex] });
    currentIndex = Math.floor(currentIndex / 2);
  }
  return { targetHash: tree.leaves[index], rootHash: tree.root, index, totalLeaves: tree.leaves.length, path };
}

export function verifyMerkleProof(proof: MerkleProof): boolean {
  if (!Number.isInteger(proof.index) || proof.index < 0 || proof.index >= proof.totalLeaves || proof.totalLeaves <= 0) return false;
  let current = proof.targetHash;
  for (const step of proof.path) current = step.position === "left" ? hashPair(step.hash, current) : hashPair(current, step.hash);
  return current === proof.rootHash;
}

export type AuditProofBundle = {
  schema: "GNW.AuditProofBundle.v2";
  taskId: number;
  generatedAt: number;
  totalEvents: number;
  complete: boolean;
  completenessReason: string;
  merkleRoot: string;
  genesisHash: string;
  finalHash: string;
  chainValid: boolean;
  signature?: { issuer: string; signature: string };
  events: Array<{ id: number; eventType: string; decision: string; reason: string; eventHash: string; merkleProof: MerkleProof }>;
};

function bundleSigningPayload(bundle: Omit<AuditProofBundle, "signature">): string {
  return canonicalize(bundle);
}

export function signAuditBundle(bundle: Omit<AuditProofBundle, "signature">, issuer: string, privateKeyPem: string): AuditProofBundle {
  const signature = cryptoSign(null, Buffer.from(bundleSigningPayload(bundle)), createPrivateKey(privateKeyPem)).toString("base64url");
  return { ...bundle, signature: { issuer, signature } };
}

export function verifyAuditBundleSignature(bundle: AuditProofBundle, publicKeyPem: string): boolean {
  if (!bundle.signature) return false;
  const { signature, ...unsigned } = bundle;
  try { return cryptoVerify(null, Buffer.from(bundleSigningPayload(unsigned)), createPublicKey(publicKeyPem), Buffer.from(signature.signature, "base64url")); } catch { return false; }
}

export function verifyAuditProofBundle(bundle: AuditProofBundle): { valid: boolean; chain: boolean; merkle: boolean; complete: boolean; errors: string[] } {
  const errors: string[] = [];
  const merkle = bundle.events.every(event => verifyMerkleProof(event.merkleProof) && event.merkleProof.rootHash === bundle.merkleRoot && event.eventHash === event.merkleProof.targetHash);
  const complete = bundle.complete && bundle.totalEvents === bundle.events.length;
  if (!bundle.chainValid) errors.push("audit_chain_invalid");
  if (!merkle) errors.push("merkle_invalid");
  if (!complete) errors.push("evidence_incomplete");
  return { valid: bundle.chainValid && merkle && complete, chain: bundle.chainValid, merkle, complete, errors };
}

/** Exports complete, not capped, proof material. A signed bundle is optional until issuer keys are configured. */
export async function exportAuditProofBundle(db: Db, taskId: number, signing?: { issuer: string; privateKeyPem: string }): Promise<AuditProofBundle> {
  const events: AuditRow[] = await listAuditComplete(db, taskId);
  const chain = await verifyAuditChain(db);
  const leafHashes = events.map(e => e.event_hash);
  const tree = buildMerkleTree(leafHashes);
  const unsigned: Omit<AuditProofBundle, "signature"> = {
    schema: "GNW.AuditProofBundle.v2",
    taskId,
    generatedAt: Date.now(),
    totalEvents: events.length,
    complete: chain.valid && events.length === leafHashes.length,
    completenessReason: chain.valid ? "all_task_events_retrieved_without_limit" : "global_audit_chain_invalid",
    merkleRoot: tree.root,
    genesisHash: events[0]?.previous_hash ?? GENESIS_HASH,
    finalHash: events[events.length - 1]?.event_hash ?? tree.root,
    chainValid: chain.valid,
    events: events.map((event, idx) => ({ id: event.id, eventType: event.event_type, decision: event.decision, reason: event.reason, eventHash: event.event_hash, merkleProof: generateMerkleProof(tree, idx) })),
  };
  return signing ? signAuditBundle(unsigned, signing.issuer, signing.privateKeyPem) : unsigned;
}
