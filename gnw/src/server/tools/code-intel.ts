import type { Db } from "../db/index.js";
import type { Env } from "../env.js";
import type { SessionUser } from "../auth.js";
import type { CapabilityLease } from "../capability.js";
import { executeExternal } from "../execution.js";
import { TaskSandbox } from "../sandbox/index.js";

export type CodeSymbol = {
  name: string;
  kind: "function" | "class" | "interface" | "type" | "variable" | "constant";
  file: string;
  line: number;
  signature?: string;
  isExported: boolean;
};

export type CodeSymbolsResult = {
  file?: string;
  symbols: CodeSymbol[];
  totalFound: number;
};

export type DefinitionResult = {
  symbol: string;
  found: boolean;
  definition?: CodeSymbol;
  contextSnippet?: string;
};

export function extractSymbolsFromCode(code: string, filePath: string): CodeSymbol[] {
  const symbols: CodeSymbol[] = [];
  const lines = code.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    const lineNum = i + 1;
    const isExported = line.startsWith("export ");

    const fnMatch = /(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)/.exec(line);
    if (fnMatch) {
      symbols.push({
        name: fnMatch[1],
        kind: "function",
        file: filePath,
        line: lineNum,
        signature: `function ${fnMatch[1]}(${fnMatch[2]})`,
        isExported,
      });
      continue;
    }

    const classMatch = /(?:export\s+)?class\s+([a-zA-Z0-9_$]+)/.exec(line);
    if (classMatch) {
      symbols.push({
        name: classMatch[1],
        kind: "class",
        file: filePath,
        line: lineNum,
        signature: `class ${classMatch[1]}`,
        isExported,
      });
      continue;
    }

    const ifaceMatch = /(?:export\s+)?interface\s+([a-zA-Z0-9_$]+)/.exec(line);
    if (ifaceMatch) {
      symbols.push({
        name: ifaceMatch[1],
        kind: "interface",
        file: filePath,
        line: lineNum,
        signature: `interface ${ifaceMatch[1]}`,
        isExported,
      });
      continue;
    }

    const typeMatch = /(?:export\s+)?type\s+([a-zA-Z0-9_$]+)\s*=/.exec(line);
    if (typeMatch) {
      symbols.push({
        name: typeMatch[1],
        kind: "type",
        file: filePath,
        line: lineNum,
        signature: `type ${typeMatch[1]}`,
        isExported,
      });
      continue;
    }

    const arrowMatch = /(?:export\s+)?const\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>/.exec(line);
    if (arrowMatch) {
      symbols.push({
        name: arrowMatch[1],
        kind: "function",
        file: filePath,
        line: lineNum,
        signature: `const ${arrowMatch[1]} = (${arrowMatch[2]}) =>`,
        isExported,
      });
      continue;
    }
  }

  return symbols;
}

export async function runGovernedFindSymbols(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  filePath?: string;
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<CodeSymbolsResult> {
  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "code_symbols",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "code.symbols",
    effect: async () => {
      const sandbox = new TaskSandbox(p.taskId, p.env.artifactDir ? `${p.env.artifactDir}/sandboxes` : "./data/sandboxes");
      await sandbox.init();

      const symbols: CodeSymbol[] = [];

      if (p.filePath) {
        const content = await sandbox.readFile(p.filePath);
        symbols.push(...extractSymbolsFromCode(content, p.filePath));
      } else {
        const files = await sandbox.listFiles("");
        for (const file of files.slice(0, 30)) {
          if (/\.(ts|tsx|js|jsx|py|go)$/.test(file)) {
            try {
              const content = await sandbox.readFile(file);
              symbols.push(...extractSymbolsFromCode(content, file));
            } catch {
              // Ignore unreadable files
            }
          }
        }
      }

      return {
        file: p.filePath,
        symbols: symbols.slice(0, 100),
        totalFound: symbols.length,
      };
    },
  });
}

export async function runGovernedFindDefinition(p: {
  db: Db;
  env: Env;
  user: SessionUser;
  taskId: number;
  symbolName: string;
  actionDigest: string;
  capabilityLease: CapabilityLease;
}): Promise<DefinitionResult> {
  return executeExternal({
    db: p.db,
    env: p.env,
    taskId: p.taskId,
    actorUserId: p.user.id,
    eventType: "code_definition",
    actionDigest: p.actionDigest,
    capabilityLease: p.capabilityLease,
    capability: "code.definition",
    effect: async () => {
      const sandbox = new TaskSandbox(p.taskId, p.env.artifactDir ? `${p.env.artifactDir}/sandboxes` : "./data/sandboxes");
      await sandbox.init();

      const files = await sandbox.listFiles("");
      for (const file of files) {
        if (/\.(ts|tsx|js|jsx|py|go)$/.test(file)) {
          try {
            const content = await sandbox.readFile(file);
            const symbols = extractSymbolsFromCode(content, file);
            const match = symbols.find(s => s.name === p.symbolName);
            if (match) {
              const lines = content.split("\n");
              const start = Math.max(0, match.line - 2);
              const end = Math.min(lines.length, match.line + 4);
              const contextSnippet = lines.slice(start, end).join("\n");

              return {
                symbol: p.symbolName,
                found: true,
                definition: match,
                contextSnippet,
              };
            }
          } catch {
            // Ignore unreadable files
          }
        }
      }

      return {
        symbol: p.symbolName,
        found: false,
      };
    },
  });
}
