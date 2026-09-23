import fs from "node:fs";
import { verifyAuditBundleSignature, verifyAuditProofBundle, type AuditProofBundle } from "../src/server/merkle.js";

const [file, publicKeyFile] = process.argv.slice(2);
if (!file) {
  console.error("usage: npm run gnw:verify -- proof.gnwproof [issuer-public-key.pem]");
  process.exit(2);
}

const bundle = JSON.parse(fs.readFileSync(file, "utf8")) as AuditProofBundle;
const result = verifyAuditProofBundle(bundle);
const signature = publicKeyFile ? verifyAuditBundleSignature(bundle, fs.readFileSync(publicKeyFile, "utf8")) : !bundle.signature;
const output = {
  schema: bundle.schema,
  taskId: bundle.taskId,
  AUTHORITY: "NOT_IN_BUNDLE",
  ACTION_DIGEST: "NOT_IN_BUNDLE",
  AUDIT_CHAIN: result.chain ? "VALID" : "INVALID",
  MERKLE: result.merkle ? "VALID" : "INVALID",
  SIGNATURE: signature ? "VALID" : "INVALID_OR_UNVERIFIED",
  COMPLETENESS: result.complete ? "VALID" : "INCOMPLETE",
  FINAL: result.valid && signature ? "VALID" : result.errors.includes("evidence_incomplete") ? "INCOMPLETE" : "INVALID",
  errors: result.errors,
};
console.log(JSON.stringify(output, null, 2));
process.exit(output.FINAL === "VALID" || output.FINAL === "INCOMPLETE" ? 0 : 1);
