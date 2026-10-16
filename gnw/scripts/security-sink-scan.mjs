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

// External LLM, webhook, and video sinks use the durable-fence wrapper.
// Accept the current executeFencedExternal() boundary rather than incorrectly
// requiring the older executeExternal() name.
const executionCallers = files.filter(file => /\\bexecute(?:Fenced)?External\\s*\\(/.test(source.get(file)));
const externalModules = [
  { name: "llm.ts", boundary: "executeFencedExternal" },
  { name: "video.ts", boundary: "executeFencedExternal" },
  { name: "notify.ts", boundary: "executeFencedExternal" },
  { name: "storage.ts", boundary: null },
].map(item => ({ ...item, file: path.join(root, item.name) }));
const missingExternalBoundary = externalModules.filter(({ file, boundary }) => {
  const text = source.get(file) ?? "";
  return !text.includes("governedFetch") || (boundary !== null && !text.includes(boundary));
});
if (missingExternalBoundary.length) {
  console.error("FAIL: expected external modules are missing governed egress or their required execution boundary.");
  for (const item of missingExternalBoundary) {
    console.error(`missing_external_boundary=${item.file} required=${item.boundary ?? "governedFetch"}`);
  }
  process.exit(2);
}

console.log(`PASS: raw_fetch_sinks=${rawFetchFiles.length}; governed_fetch_sinks=${governedFetchFiles.length}; execution_boundary_modules=${executionCallers.length}.`);
