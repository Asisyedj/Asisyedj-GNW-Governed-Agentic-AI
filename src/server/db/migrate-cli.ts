import { ENV } from "../env.js";
import { createDb, migrate } from "./index.js";

const db = await createDb(ENV.databaseUrl);
await migrate(db);
await db.close();
console.log(`[migrate] schema applied to ${ENV.databaseUrl.replace(/:[^:@/]+@/, ":****@")}`);
