import { generateKeyPairSync } from 'node:crypto';
const { privateKey, publicKey } = generateKeyPairSync('ed25519', { privateKeyEncoding: { type: 'pkcs8', format: 'pem' }, publicKeyEncoding: { type: 'spki', format: 'pem' } });
console.log('GNW_GRANT_PRIVATE_KEY_PEM=' + JSON.stringify(privateKey));
console.log('GNW_GRANT_PUBLIC_KEY_PEM=' + JSON.stringify(publicKey));
