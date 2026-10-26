# Perplexity Browser Session → Local OpenAI-compatible API (Setup Guide)

Ye setup aapke Perplexity account ke **browser session** ko ek local API server mein convert karta hai,
taaki aapko **official Perplexity API key kharidne ki zaroorat na pade**.

Support: `perplexity-webui-scraper==1.2.1` | Python 3.14 | Windows  
Project: `D:\GNW\perplexity-browser-api`

> **SECURITY CORRECTION — 2026-10-24:** This is a legacy third-party scraper guide, not the active GNW bridge runbook. Do **not** follow the old directions below to copy `__Secure-next-auth.session-token` into a `.env` file or paste browser cookies into terminal commands. The current GNW runtime uses a user-scoped Windows DPAPI-protected `perplexity-session.dpapi` via `gnw_secrets.py`; use the approved provisioning path for that store. The separate `bridge-api-key.txt` is currently a user-local text file consumed by OpenCode; `seal.json` provides an integrity digest, **not encryption**. Do not claim this key is DPAPI-protected or that file length proves 256-bit entropy. For production, prefer a supported official API and its approved secret manager.

---

## Step 1 — Environment ready ho gaya (verify)

Neender package install ho chuka hai. Confirm karne ke liye:

```powershell
cd D:\GNW\perplexity-browser-api
uv run perplexity-webui-scraper --help
```

Aapko teen commands dikheni chahiye: `token`, `api`, `mcp`.

---

## Step 2 — Legacy token instructions (superseded; do not use for GNW)

The browser-cookie extraction instructions that used to appear in this section have been intentionally withdrawn. Do not inspect/copy browser cookies or place a live session token in `.env`, shell history, logs, tickets, or audit reports. For an already-provisioned GNW machine, the runtime reads the DPAPI-protected session through `gnw_secrets.get_session_token()`. If the DPAPI secret is missing or expired, use the owner-approved session refresh/provisioning workflow; never bypass the protected store by falling back to plaintext `.env`.

> **Free account:** sirf text prompts chalenge. Pro/Max model aur file upload ke liye paid subscription chahiye.  
> **Risk:** Yeh unofficial reverse-engineered endpoint hai. Perplexity kabhi bhi API badal sakta hai, cookie revoke kar sakta hai, ya account suspend kar sakta hai. Personal use ke liye OK; production ke liye official API use karein.

---

## Step 3 — Legacy `.env` setup (superseded)

Do not create a new GNW `.env` containing `PERPLEXITY_SESSION_TOKEN`. The active bridge obtains the session from the DPAPI-backed store and uses the scoped local bridge key. Configure only non-secret settings that the exact deployed component documents. Never place a browser token, bridge key, or cookie into source control, chat, audit output, or command history.

---

## Step 4 — Current GNW bridge (legacy standalone command withdrawn)

Do not start the third-party `perplexity-webui-scraper api` command over the active GNW service. It may bypass the GNW DPAPI session store, bind an unexpected token flow, or collide with the port already used by the governed bridge. The current local compatibility bridge is bound to `127.0.0.1:8000`; use the existing managed service and inspect only its non-secret `/health` status. Never submit a session token as a request header for routine diagnostics.

---

## Step 5 — Safe API diagnostics

Never put the Perplexity session token into `$env:PERPLEXITY_SESSION_TOKEN`, a copied curl command, shell history, or a report. The safe project test is `test_api.py`, which retrieves the scoped bridge key through the approved local accessor and suppresses response bodies/credentials. A successful `/v1/models` response proves catalog access only; a separate model smoke is needed to prove a model is callable.

---

## Step 6 — `test_api.py` (GNW bridge smoke test)

```powershell
cd D:\GNW\perplexity-browser-api
.\.venv\Scripts\python.exe test_api.py
```

This test uses the project's protected bridge-key accessor, discards error bodies, and records only HTTP status / model count / response length. It must never require a pasted browser token or a `.env` session-token entry.

---

## Follow-up queries (context) kaise rakhein

Library automatically `previous_response_id` ke through conversation thread manage karti hai (OpenAI Responses API style). OpenAI SDK se `previous_response_id` pass karke follow-up kar sakte hain.

---

## Troubleshooting

| Problem | Samadhan |
|---------|----------|
| `401 Unauthorized` | Bridge authorization failed. Check the non-secret status/seal metadata and use the approved DPAPI-backed session refresh procedure. Do not copy a cookie into `.env` or print credentials. |
| `ModelAccessError` | Free account pe Pro model maang rahe hain. `model="perplexity/best"` ya free-tier model use karein. |
| `Cloudflare 403` / document upload fail | Perplexity ka attachment endpoint abhi Cloudflare se block ho sakta hai (known issue, Oct 2026). Sirf text chat try karein. |
| Server start nahi hota | Port 8000 pe kuch aur chal raha ho sakta hai. `--port 8001` try karein. |

---

## Session refresh and recovery

If the DPAPI session becomes invalid, follow the owner-approved refresh/provisioning procedure that calls `gnw_secrets.set_session_token()` after secure interactive acquisition. Do not scrape/copy cookie values into documentation, terminal history, environment files, or chat. The DPAPI blob is user-scoped to the Windows account that created it; recovery must run under that same account or use the approved re-provisioning workflow. The bridge key is currently a separate local text file, so restrict its Windows ACL and do not treat its integrity seal as encryption.
