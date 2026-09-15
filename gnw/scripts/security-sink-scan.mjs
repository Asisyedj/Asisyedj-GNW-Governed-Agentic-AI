import fs from "node:fs";
import path from "node:path";

const root = path.resolve("src/server");
const files = [];
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full);
    else if (entry.name.endsWith(".ts")) files.push(full);
  }
}
walk(root);

const source = new Map(files.map(file => [file, fs.readFileSync(file, "utf8")]));
const rawFetchFiles = files.filter(file => /(?<!governed)fetch\s*\(/.test(source.get(file)));
const governedFetchFiles = files.filter(file => path.basename(file) !== "security.ts" && /\bgovernedFetch\s*\(/.test(source.get(file)));
const unsafeNetworkFiles = rawFetchFiles.filter(file => !/from\s+["'](?:\.\/|\.\.\/)security\.js["']/.test(source.get(file)));
const missingGovernedImport = governedFetchFiles.filter(file => !/from\s+["'](?:\.\/|\.\.\/)security\.js["']/.test(source.get(file)));

if (unsafeNetworkFiles.length || missingGovernedImport.length) {
  console.error("FAIL: network sinks are not routed through the governed egress helper.");
  if (unsafeNetworkFiles.length) console.error(`raw_fetch_without_security_import=${unsafeNetworkFiles.join(",")}`);
  if (missingGovernedImport.length) console.error(`governed_fetch_without_security_import=${missingGovernedImport.join(",")}`);
  process.exit(2);
}

// Both the legacy central boundary and the durable provider-fencing boundary
// are valid execution gates.  A fenced call is deliberately not required to
// contain the shorter legacy token as a substring: the production gate must
// recognize the actual exported helper name.
const executionCallers = files.filter(file => /execute(?:Fenced)?External\s*\(/.test(source.get(file)));
const externalModules = ["llm.ts", "video.ts", "notify.ts", "storage.ts"].map(name => path.join(root, name));
const missingExternalBoundary = externalModules.filter(file => {
  const text = source.get(file) ?? "";
  const hasExecutionBoundary = text.includes("executeExternal") || text.includes("executeFencedExternal");
  return !text.includes("governedFetch") || (path.basename(file) !== "storage.ts" && !hasExecutionBoundary);
});
if (missingExternalBoundary.length) {
  console.error(`FAIL: expected external modules lack both governedFetch and executeExternal: ${missingExternalBoundary.join(",")}`);
  process.exit(2);
}

console.log(`PASS: raw_fetch_sinks=${rawFetchFiles.length}; governed_fetch_sinks=${governedFetchFiles.length}; execution_boundary_modules=${executionCallers.length}.`);
