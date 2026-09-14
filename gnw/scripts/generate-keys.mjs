import { generateKeyPairSync } from "node:crypto";

const { privateKey, publicKey } = generateKeyPairSync("ed25519", {
  privateKeyEncoding: { type: "pkcs8", format: "pem" },
  publicKeyEncoding: { type: "spki", format: "pem" },
});

console.log("\n================ GNW ED25519 KEYS FOR PRODUCTION ================\n");
console.log("Copy these to your Vercel Environment Variables or .env:\n");
console.log("GNW_GRANT_PRIVATE_KEY_PEM=\"\\");
console.log(privateKey.trim().replace(/\n/g, "\\n") + "\"");
console.log("\nGNW_GRANT_PUBLIC_KEY_PEM=\"\\");
console.log(publicKey.trim().replace(/\n/g, "\\n") + "\"");
console.log("\n=================================================================\n");
