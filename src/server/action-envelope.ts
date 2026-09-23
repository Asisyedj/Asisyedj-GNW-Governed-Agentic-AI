import { canonicalize, sha256, signGrant, verifyGrantSignature } from "./security.js";

export type ProvenanceSource = "MODEL" | "CLIENT" | "GNW" | "AUTHORITY" | "EXECUTOR" | "EXTERNAL";

export type Provenanced<T> = {
  value: T;
  source: ProvenanceSource;
  trust: "UNTRUSTED" | "CLIENT_ASSERTED" | "GNW_DERIVED" | "AUTHORITY_VERIFIED" | "EXECUTOR_ATTESTED";
};

export type ActionEnvelopeV1 = {
  schema: "GNW.ActionEnvelope.v1";
  actionId: string;
  requestId: string;
  tenant: string;
  actor: string;
  agent: string;
  tool: string;
  operation: string;
  resource: string;
  parametersDigest: string;
  purpose: string;
  classification: string;
  risk: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  policy: string;
  approval?: { id: string; digest: string; expiresAt: number; reviewer: string } | null;
  capability?: { id: string; nonce: string; audience: string; expiresAt: number } | null;
  generation?: { provider?: string; model?: string; version?: string } | null;
  budget: { tokens: number; bytes: number };
  effectConstraints: Record<string, unknown>;
  timestamps: { issuedAt: number; expiresAt: number };
  nonce: string;
  provenance: Record<string, Provenanced<unknown>>;
};

export type SignedActionEnvelope = ActionEnvelopeV1 & { actionDigest: string; issuer?: string; signature?: string };

export function actionEnvelopePayload(envelope: ActionEnvelopeV1): string {
  return canonicalize(envelope);
}

export function digestActionEnvelope(envelope: ActionEnvelopeV1): string {
  return sha256(`GNW-ACTION-ENVELOPE-V1|${actionEnvelopePayload(envelope)}`);
}

export function createActionEnvelope(input: Omit<ActionEnvelopeV1, "schema" | "parametersDigest"> & { parameters: unknown }): ActionEnvelopeV1 {
  const { parameters, ...rest } = input;
  return {
    schema: "GNW.ActionEnvelope.v1",
    ...rest,
    parametersDigest: sha256(`GNW-PARAMETERS-V1|${canonicalize(parameters)}`),
  };
}

export function signActionEnvelope(envelope: ActionEnvelopeV1, issuer: string, privateKeyPem: string): SignedActionEnvelope {
  const actionDigest = digestActionEnvelope(envelope);
  const signed = signGrant({ envelope, actionDigest }, issuer, privateKeyPem);
  return { ...envelope, actionDigest, issuer: signed.issuer, signature: signed.signature };
}

export function verifySignedActionEnvelope(signed: SignedActionEnvelope, publicKeyPem: string): boolean {
  const { actionDigest, issuer, signature, ...envelope } = signed;
  if (!issuer || !signature || actionDigest !== digestActionEnvelope(envelope)) return false;
  return verifyGrantSignature({ envelope, actionDigest }, issuer, signature, publicKeyPem);
}

export function approvalMatchesAction(approval: { actionDigest: string; expiresAt: number }, envelope: ActionEnvelopeV1, now = Date.now()): boolean {
  return approval.expiresAt > now && approval.actionDigest === digestActionEnvelope(envelope);
}
