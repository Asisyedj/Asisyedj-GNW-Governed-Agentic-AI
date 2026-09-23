import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";

const rootDir = process.cwd();
const stagingDir = path.join(rootDir, "dist", "staging_pkg");
const zipName = "GNW-Governed-Agent-v4-Production.zip";
const outputZip = path.join(rootDir, zipName);
const downloadsZip = path.join(path.dirname(rootDir), zipName);

console.log("=================================================================");
console.log("   PACKAGING GNW-GOVERNED-AGENT-V4 PRODUCTION DISTRIBUTION ZIP   ");
console.log("=================================================================\n");

// 1. Clean previous staging & zip files
if (fs.existsSync(stagingDir)) fs.rmSync(stagingDir, { recursive: true, force: true });
if (fs.existsSync(outputZip)) fs.rmSync(outputZip, { force: true });
fs.mkdirSync(stagingDir, { recursive: true });

// 2. Define list of items to include
const itemsToInclude = [
  "src",
  "api",
  "docs",
  "tests",
  "scripts",
  "package.json",
  "package-lock.json",
  "tsconfig.json",
  "vite.config.ts",
  "vitest.config.ts",
  "vercel.json",
  "README.md",
  "ARCHITECTURE.md",
  "SECURITY_BASELINE.md",
  "ACCEPTANCE.md",
  "DEPLOYMENT.md",
  "DEPLOYMENT-VERCEL.md",
  "Dockerfile",
  "docker-compose.yml",
  "docker-compose.production.yml",
  ".dockerignore",
  "release/GNW-FORCE-GATE-POLICY-2026-09-21.json",
  "release/RELEASE-EVIDENCE.json",
  "release/PROVENANCE-REBOUND-2026-09-21.json",
  "docs/security/GNW-FORCE-FAIL-CLOSED-RULES-2026-09-21.md",
  ".env.example",
  ".env.production.example",
];

console.log("Copying production assets to staging area...");

for (const item of itemsToInclude) {
  const srcPath = path.join(rootDir, item);
  const destPath = path.join(stagingDir, item);

  if (!fs.existsSync(srcPath)) {
    console.warn(`[SKIP] Missing item: ${item}`);
    continue;
  }

  const stat = fs.statSync(srcPath);
  if (stat.isDirectory()) {
    fs.cpSync(srcPath, destPath, {
      recursive: true,
      filter: (source) => {
        // Exclude unwanted temp or test runtime dirs
        return !source.includes("node_modules") &&
               !source.includes(".git") &&
               !source.endsWith(".db") &&
               !source.endsWith(".log");
      },
    });
    console.log(` + Directory: ${item}`);
  } else {
    fs.mkdirSync(path.dirname(destPath), { recursive: true });
    fs.copyFileSync(srcPath, destPath);
    console.log(` + File:      ${item}`);
  }
}

// 3. Compress using portable zip (Linux/macOS/CI friendly).
console.log("\nCompressing into production ZIP archive...");
try {
  execFileSync("zip", ["-q", "-r", "-X", outputZip, "."], { cwd: stagingDir, stdio: "inherit" });
} catch (error) {
  console.error("zip command is required for deterministic distribution packaging");
  throw error;
}

// 3a. Refuse forbidden runtime/development material in the artifact.
const listing = execFileSync("unzip", ["-Z1", outputZip], { encoding: "utf8" });
const forbidden = listing.split(/\r?\n/).filter((entry) =>
  /(^|\/)(node_modules|\.git)(\/|$)|(^|\/)(.*\.(?:log|db|pem|key))$|(^|\/)\.env(?:\.|$)/i.test(entry)
);
if (forbidden.length) {
  console.error("FORBIDDEN ARTIFACT CONTENT:");
  for (const entry of forbidden) console.error(` - ${entry}`);
  throw new Error("distribution contains forbidden runtime/development material");
}

// 4. Also copy to Downloads folder for immediate user convenience
try {
  fs.copyFileSync(outputZip, downloadsZip);
  console.log(` + Also saved copy to: ${downloadsZip}`);
} catch (err) {
  // Optional copy
}

// 5. Compute SHA256 checksum and size
const fileBuffer = fs.readFileSync(outputZip);
const sha256 = createHash("sha256").update(fileBuffer).digest("hex");
const sizeMb = (fileBuffer.length / (1024 * 1024)).toFixed(2);

// 6. Clean staging directory
fs.rmSync(stagingDir, { recursive: true, force: true });

console.log("\n=================================================================");
console.log("   PRODUCTION DISTRIBUTION PACKAGE CREATED SUCCESSFULLY!        ");
console.log("=================================================================");
console.log(` Archive Path: ${outputZip}`);
console.log(` Size:         ${sizeMb} MB (${fileBuffer.length.toLocaleString()} bytes)`);
console.log(` SHA-256:      ${sha256}`);
console.log("=================================================================\n");
