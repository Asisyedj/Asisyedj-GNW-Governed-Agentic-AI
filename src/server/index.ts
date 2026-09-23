import { createApp } from "./app.js";
import { bootstrapOwner } from "./auth.js";
import { getDb } from "./db/index.js";
import { ENV, assertProductionEnvironment, readinessReport } from "./env.js";

async function main() {
  assertProductionEnvironment(ENV);
  const db = await getDb(ENV);
  await bootstrapOwner(db, ENV);
  const app = await createApp(ENV, Promise.resolve(db));
  const report = readinessReport(ENV);

  const server = app.listen(ENV.port, () => {
    console.log(JSON.stringify({ level: "info", event: "server_started", port: ENV.port, env: ENV.nodeEnv, ready: report.ready, checks: report.checks }));
  });

  const shutdown = (signal: string) => {
    console.log(JSON.stringify({ level: "info", event: "shutdown", signal }));
    server.close(async () => {
      await db.close().catch(() => undefined);
      process.exit(0);
    });
    setTimeout(() => process.exit(1), 10_000).unref();
  };

  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("unhandledRejection", reason => console.error(JSON.stringify({ level: "error", event: "unhandled_rejection", reason: String(reason) })));
}

main().catch(error => {
  console.error(JSON.stringify({ level: "fatal", event: "startup_failed", message: error instanceof Error ? error.message : String(error) }));
  process.exit(1);
});
