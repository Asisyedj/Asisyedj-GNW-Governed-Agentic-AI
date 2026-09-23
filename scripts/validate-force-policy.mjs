import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const policy = JSON.parse(fs.readFileSync(path.join(root,"release/GNW-FORCE-GATE-POLICY-2026-09-21.json"),"utf8"));
const evidence = JSON.parse(fs.readFileSync(path.join(root,"release/RELEASE-EVIDENCE.json"),"utf8"));
const failures=[];
if (policy.default_state !== "BLOCKED") failures.push("default_state must be BLOCKED");
for (const gate of policy.required_gates) {
  const value=evidence.gates?.[gate];
  if (!value) failures.push(`${gate}=MISSING`);
}
const mandatoryPass = policy.required_gates.every(g => evidence.gates?.[g] === "PASS");
if (!mandatoryPass && evidence.production_ready === true) failures.push("production_ready=true while mandatory gates are not all PASS");
if (evidence.status === "PASS" && !mandatoryPass) failures.push("status=PASS while mandatory gates are not all PASS");
if (evidence.review?.reviewer === "UNASSIGNED" || evidence.review?.organization === "UNASSIGNED") failures.push("independent review authority is unassigned");
if (!evidence.review?.signature || evidence.review.signature === "MISSING") failures.push("review signature missing");
if (failures.length) {
  console.error("FORCE POLICY: BLOCKED");
  for (const f of failures) console.error(` - ${f}`);
  process.exit(2);
}
console.log("FORCE POLICY: PASS");
