# GNW Governed Agent v4 — Vercel Deployment Guide
# ورسل (Vercel) پر ڈپلائمنٹ کا طریقہ کار

This guide explains how to deploy **GNW-Governed-Agent-v4** to Vercel in production with PostgreSQL, Ed25519 cryptographic signing, and full fail-closed governance.

---

## 1. Prerequisites / ضروری معلومات
1. **Vercel Account**: Free or Pro account at [vercel.com](https://vercel.com).
2. **PostgreSQL Database**:
   - Vercel Serverless Functions are stateless, so a persistent PostgreSQL database is required.
   - Recommended options (All have free tiers):
     - **Vercel Postgres** (Directly in Vercel Storage tab)
     - **Neon Postgres** ([neon.tech](https://neon.tech))
     - **Supabase** ([supabase.com](https://supabase.com))
     - **Railway** ([railway.app](https://railway.app))

---

## 2. Option A: Deploy using Vercel CLI (کمانڈ لائن سے ڈپلائمنٹ)

### Step 1: Login to Vercel
Open your terminal in the project directory and run:
```bash
npx vercel login
```
Follow the prompt in your browser to authenticate.

### Step 2: Link Project
```bash
npx vercel
```
- Select "Set up and deploy?" -> **Y**
- Which scope? -> Select your account
- Link to existing project? -> **N**
- What's your project's name? -> `gnw-governed-agent`
- In which directory is your code located? -> `./`
- Want to modify settings? -> **N**

### Step 3: Configure Environment Variables
Set your environment variables in Vercel either via CLI or in the Vercel Dashboard:
```bash
npx vercel env add DATABASE_URL production
npx vercel env add SESSION_SECRET production
npx vercel env add OWNER_EMAIL production
npx vercel env add OWNER_PASSWORD production
npx vercel env add GNW_REQUIRE_SIGNED_GRANTS production
npx vercel env add GNW_GRANT_ISSUER production
npx vercel env add GNW_GRANT_PRIVATE_KEY_PEM production
npx vercel env add GNW_GRANT_PUBLIC_KEY_PEM production
npx vercel env add ALLOW_SELF_REGISTRATION production
```

To generate your Ed25519 signing keys, run locally:
```bash
node scripts/generate-keys.mjs
```

### Step 4: Deploy to Production
```bash
npx vercel --prod
```
Vercel will build the frontend into `dist/public`, bundle the serverless functions in `api/index.ts`, and provide you with a live URL (e.g. `https://gnw-governed-agent.vercel.app`).

---

## 3. Option B: Deploy using GitHub & Vercel Dashboard (ویب ڈیش بورڈ سے ڈپلائمنٹ)

1. Push your code (or extract the provided ZIP file) to a GitHub repository.
2. Go to [vercel.com/new](https://vercel.com/new).
3. Import your GitHub repository.
4. Framework Preset will be automatically detected as **Vite**.
5. Under **Environment Variables**, copy the values from `.env.production.example`:
   - `DATABASE_URL`: `postgres://...`
   - `SESSION_SECRET`: (min 32 characters)
   - `OWNER_EMAIL`: `admin@yourdomain.com`
   - `OWNER_PASSWORD`: `your-secure-password`
   - `ALLOW_SELF_REGISTRATION`: `false`
   - `GNW_REQUIRE_SIGNED_GRANTS`: `true`
   - `GNW_GRANT_ISSUER`: `gnw-production-issuer`
   - `GNW_GRANT_PRIVATE_KEY_PEM`: (generated from `node scripts/generate-keys.mjs`)
   - `GNW_GRANT_PUBLIC_KEY_PEM`: (generated from `node scripts/generate-keys.mjs`)
   - `GNW_ALLOWED_EGRESS_HOSTS`: `api.openai.com,api.anthropic.com`
6. Click **Deploy**.

---

## 4. Verification After Deployment (ڈپلائمنٹ کے بعد تصدیق)

Once deployed, visit your Vercel URL:
1. Navigate to `/` -> Log in with your `OWNER_EMAIL` and `OWNER_PASSWORD`.
2. Access the **Readiness Dashboard** to verify that:
   - Database connection is OK.
   - Grant signing is OK (Ed25519 verified).
   - Governance Interlock is ready.
3. Test a governed task execution and download the Merkle Audit Evidence Bundle!
