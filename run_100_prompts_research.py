"""
Comprehensive 100-Prompt Production Research Engine
Dispatches 100 deep-research prompts across the Top 10 Frontier Models via Perplexity Bridge.
Saves structured intelligence to D:/GNW/perplexity-browser-api/production_100_research_results.json
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

BRIDGE_URL = "http://127.0.0.1:8000"
SESSION_TOKEN = os.getenv("PERPLEXITY_SESSION_TOKEN", "")

PILLARS = [
    {
        "pillar_id": "P1",
        "title": "Grant Key Infrastructure (Ed25519 PKCS#8 & SPKI)",
        "model": "openai/gpt5",
        "prompts": [
            "1.1 Exact Ed25519 key generation parameters in Node.js crypto (PKCS#8 private, SPKI public PEM format).",
            "1.2 Self-signing verification protocol for payload 'GNW-GRANT-KEY-PAIR-V1' using crypto.sign and crypto.verify.",
            "1.3 Constant-time cryptographic signature verification to prevent side-channel timing attacks.",
            "1.4 Zeroization and memory sanitization patterns for private key buffers in JavaScript/Node.js.",
            "1.5 Safe key rotation strategy without revoking active in-flight tenant grants.",
            "1.6 Canonical JSON serialization (RFC 8785) for grants before digest calculation.",
            "1.7 Replay attack prevention via deterministic sequence IDs and monotonically increasing nonces.",
            "1.8 Issuer namespace validation and strict URI matching against authorized authorities.",
            "1.9 Fail-closed error handling when PEM header/footer is corrupted or has trailing whitespace.",
            "1.10 End-to-end unit test suite validating Ed25519 grant issuance, verification, and tamper rejection."
        ]
    },
    {
        "pillar_id": "P2",
        "title": "Lease Key Lifecycle & Ephemeral Tenant Isolation",
        "model": "openai/gpt-5.4",
        "prompts": [
            "2.1 Ephemeral tenant lease minting architecture with microsecond timestamps.",
            "2.2 Cryptographic binding of lease public key to tenant UUID and workspace root path.",
            "2.3 High-performance in-memory and Redis Bloom-filter CRL (Certificate Revocation List).",
            "2.4 Clock-skew tolerance algorithms balancing network jitter vs replay window limits.",
            "2.5 Concurrency-safe lease renewal without race conditions under multi-agent load.",
            "2.6 Cryptographic resurrection prevention: ensuring expired/revoked leases can never be re-activated.",
            "2.7 Secure deletion verification: validating private key zero-fill on lease termination.",
            "2.8 Sub-agent privilege degradation: hierarchical lease delegation with strictly reduced scopes.",
            "2.9 Distributed nonce tracking with sliding time-window eviction.",
            "2.10 Automated audit chain logging for every lease lifecycle state transition."
        ]
    },
    {
        "pillar_id": "P3",
        "title": "TEE Hardware Attestation & Remote Measurement Verification",
        "model": "x-ai/grok-4.7",
        "prompts": [
            "3.1 Hardware quote extraction and format standards (AMD SEV-SNP, Intel SGX, AWS Nitro Enclaves).",
            "3.2 64-hex SHA-256 measurement string validation and regex boundary enforcement.",
            "3.3 Cryptographic nonce freshness protocol preventing replay of stale hardware quotes.",
            "3.4 Temporal validity window math: verifying issuedAt <= now < expiresAt with max-age <= 120,000ms.",
            "3.5 Domain-separated payload construction: 'GNW-TEE-RELEASE-ATTESTATION-V1|{subject}|{issuer}|{measurement}|{nonce}|{issuedAt}|{expiresAt}'.",
            "3.6 Attestation public key parsing, root-of-trust verification, and hex signature decoding.",
            "3.7 Subject verification: binding attestation subject strictly to release commit SHA.",
            "3.8 Safe caching of verified attestation reports with automatic TTL eviction.",
            "3.9 Synthetic hardware attestation generator for staging and CI/CD deterministic simulation.",
            "3.10 Fail-closed rejection rules for malformed, expired, future-dated, or issuer-mismatched evidence."
        ]
    },
    {
        "pillar_id": "P4",
        "title": "MPC Trust Anchor Governance & Threshold Consensus",
        "model": "openai/gpt-5.4-thinking",
        "prompts": [
            "4.1 Shamir Secret Sharing vs threshold signature schemes (TSS / BLS) for governance release signing.",
            "4.2 Dynamic k-of-n participant threshold calculation and mathematical validity constraints.",
            "4.3 Sybil defense: verifying distinct participant cryptographic public keys in participants map.",
            "4.4 Domain-separated release digest: SHA256('GNW-RELEASE-V1|' + releaseSubject).",
            "4.5 Multi-party payload format: 'GNW-TRUST-ANCHOR-V1|{releaseDigest}|{measurement}|{nonce}'.",
            "4.6 Duplicate signature deduplication using cryptographic Set tracking on participantId.",
            "4.7 Enforcing requireTee=true and validating that hardware measurement is bound to MPC consensus.",
            "4.8 Byzantine fault tolerance: handling corrupted or malicious participant signatures without crash.",
            "4.9 Participant key rotation protocol preserving historical release audit integrity.",
            "4.10 Complete fail-closed preflight test harness for MPC evidence validation."
        ]
    },
    {
        "pillar_id": "P5",
        "title": "Release & Git Provenance Binding (SLSA Level 4)",
        "model": "perplexity/best",
        "prompts": [
            "5.1 Git commit SHA full 40-hex vs 64-hex SHA-256 format validation and regex verification.",
            "5.2 Environment resolution precedence: GNW_RELEASE_COMMIT_SHA vs GITHUB_SHA.",
            "5.3 Clean working-tree verification: detecting uncommitted changes, untracked files, and submodules.",
            "5.4 SLSA Level 3/4 provenance generation binding source commit, build workflow, and artifact hash.",
            "5.5 Cryptographic Git tag signing using GPG and Sigstore cosign keyless signing.",
            "5.6 Deterministic immutable artifact digest hashing across distributed build machines.",
            "5.7 Reproducible build verification: byte-for-byte comparison across independent build containers.",
            "5.8 Canonical release metadata JSON schema definition and cryptographic signature embedding.",
            "5.9 Automated rollback target validation: ensuring rollback commits exist in cryptographic allowlist.",
            "5.10 Pre-deployment Git release audit script verifying commit signature and CI/CD attestation."
        ]
    },
    {
        "pillar_id": "P6",
        "title": "Network Egress & SSRF Protection Architecture",
        "model": "google/gemini-3.8-flash",
        "prompts": [
            "6.1 DNS rebinding attack defense: resolving hostnames at connection time and validating IP addresses.",
            "6.2 Comprehensive private IP blocking: filtering RFC 1918, 127.0.0.0/8, 169.254.0.0/16, IPv6 ULA/link-local.",
            "6.3 Mandatory HTTPS TLS 1.3 enforcement with strict cipher suite configuration.",
            "6.4 GNW_EGRESS_ALLOW_LIST parsing: exact host, subdomain wildcard, and port matching semantics.",
            "6.5 HTTP redirect security: preventing cross-protocol downgrades (HTTPS->HTTP) and limit to max 3 hops.",
            "6.6 Connection timeouts (max 5s connect, 30s read) and maximum response payload size limits (10MB).",
            "6.7 Outbound proxy configuration and network namespace isolation in containerized deployment.",
            "6.8 Immutable audit logging of all external HTTP requests with request hash and response status.",
            "6.9 Circuit-breaker design: tripping offline mode upon 3 consecutive network egress violations.",
            "6.10 Air-gapped fallback mode: operating local verification without external network dependency."
        ]
    },
    {
        "pillar_id": "P7",
        "title": "Database Hardening, SSL Closure & RLS Multi-Tenant Isolation",
        "model": "anthropic/claude-sonnet-5.5",
        "prompts": [
            "7.1 PostgreSQL connection string parsing with mandatory 'sslmode=verify-full' enforcement.",
            "7.2 Server root CA certificate verification and custom certificate bundle configuration.",
            "7.3 Connection pool hardening: connection timeouts, statement timeouts, and maximum connection caps.",
            "7.4 Row Level Security (RLS) policy architecture: tenant isolation on every table with zero bypass.",
            "7.5 Append-only invariant enforcement: blocking UPDATE, DELETE, and TRUNCATE on audit tables via Postgres triggers.",
            "7.6 Parameterized SQL query patterns: 100% elimination of SQL injection vulnerabilities.",
            "7.7 Schema migration runner with explicit lock timeout, statement timeout, and transactional rollback.",
            "7.8 Database health probe with active read-after-write verification.",
            "7.9 Cross-tenant negative security test suite verifying that Tenant A cannot access Tenant B data.",
            "7.10 Fail-closed disaster recovery: automated rollback upon migration verification failure."
        ]
    },
    {
        "pillar_id": "P8",
        "title": "Secret Entropy, Cookie Security & Session Hardening",
        "model": "anthropic/claude-sonnet-5",
        "prompts": [
            "8.1 CSPRNG 256-bit entropy generation using crypto.randomBytes(32) for all production secrets.",
            "8.2 HMAC-SHA256 cookie signing and tamper detection protocol.",
            "8.3 Secure session token storage: SHA-256 hashing before storing session identifiers in database.",
            "8.4 Production cookie flags: HttpOnly=true, Secure=true, SameSite=Strict, Path=/.",
            "8.5 Zero-downtime secret rotation protocol supporting current and previous secret keys.",
            "8.6 Environment variable leakage prevention: scrubbing secrets from process dumps, logs, and error traces.",
            "8.7 Constant-time secret comparison (crypto.timingSafeEqual) to prevent timing side-channels.",
            "8.8 Brute-force protection: IP-based and session-based sliding-window rate limiting.",
            "8.9 Session idle timeout (15 min) and absolute session expiration (12 hours) enforcement.",
            "8.10 Automated secret generator script creating production-ready 256-bit entropy configurations."
        ]
    },
    {
        "pillar_id": "P9",
        "title": "Atomic Shared Storage & State Concurrency Control",
        "model": "z-ai/glm-5.3",
        "prompts": [
            "9.1 Dual-driver storage architecture: seamless switching between 'local' and 's3' storage drivers.",
            "9.2 POSIX-compliant atomic file write pattern: write to temp file + fsync + atomic rename.",
            "9.3 Advisory and mandatory file locking mechanisms preventing concurrent write corruption.",
            "9.4 Directory traversal defense: sanitizing paths against '..', null bytes (%00), and symlink jumps.",
            "9.5 AWS S3 production policy enforcement: SSE-KMS encryption, versioning, and bucket policies.",
            "9.6 GNW_SHARED_STORAGE_CONFIRMED validation ensuring shared storage exists before startup.",
            "9.7 Multi-process race condition prevention for state snapshots and audit logs.",
            "9.8 Cryptographic integrity hashing (SHA-256) of every stored blob upon read and write.",
            "9.9 Storage quota and disk space monitoring interlocks with automatic halt on low disk space.",
            "9.10 Automated orphaned temporary file cleanup daemon running on scheduled cron."
        ]
    },
    {
        "pillar_id": "P10",
        "title": "Fail-Closed Preflight Engine & Unified Production Closure",
        "model": "anthropic/claude-sonnet-4.6",
        "prompts": [
            "10.1 Complete fail-closed preflight validation engine aggregating all 38 production requirements.",
            "10.2 Strict parseJsonObject enforcement rejecting null, boolean, primitive, and array inputs.",
            "10.3 Preflight execution sequence: env validation -> crypto verification -> TEE proof -> MPC quorum.",
            "10.4 Deterministic error reporting: printing explicit 'DENY' with sorted failure list on any violation.",
            "10.5 Exit code semantics: exit code 0 on 100% PASS, exit code 1 on ANY single failure.",
            "10.6 Automated test harness executing positive tests (all valid) and 38 negative tests (each failure).",
            "10.7 Invariant engine verification: ensuring immutable snapshot integrity before launching server.",
            "10.8 Production deployment orchestrator binding all environment variables and running preflight.",
            "10.9 Continuous compliance auditing: periodic re-validation of preflight invariants during runtime.",
            "10.10 Final production readiness certification report generator."
        ]
    }
]

def query_model(model_name: str, pillar_title: str, subprompts: list) -> str:
    print(f"\n=======================================================")
    print(f"DISPATCHING PILLAR: {pillar_title}")
    print(f"MODEL: {model_name} (10 Sub-Prompts)")
    print(f"=======================================================")

    formatted_prompts = "\n".join(subprompts)
    full_prompt = f"""You are a Principal Security Architect executing deep technical research for GNW Production Closure.
Topic: {pillar_title}

Address each of the following 10 research sub-vectors with rigorous, production-grade technical detail:
{formatted_prompts}

Format your response with clear numbered sections (1 to 10), providing:
- Architectural specifications and RFC/NIST standards.
- Production-ready TypeScript/Node.js/SQL code implementations.
- Fail-closed security invariants and validation assertions.
Be exhaustive, precise, and authoritative.
"""

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a World-Class Principal Security Architect and Cryptographer. Provide exhaustive, production-grade technical implementations."},
            {"role": "user", "content": full_prompt}
        ],
        "stream": False
    }

    req_data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SESSION_TOKEN}"
    }

    req = urllib.request.Request(
        f"{BRIDGE_URL}/v1/chat/completions",
        data=req_data,
        headers=headers,
        method="POST"
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - t0
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                print(f"[SUCCESS] {model_name} completed research in {elapsed:.1f}s ({len(content)} chars)")
                return content
            return f"Error: No choices returned: {data}"
    except Exception as e:
        print(f"[ERROR] {model_name}: {e}")
        return f"Error querying {model_name}: {e}"

def main():
    print(f"Starting 100-Prompt Deep Research across 10 Frontier Models...")
    results = {}

    for pillar in PILLARS:
        p_id = pillar["pillar_id"]
        title = pillar["title"]
        model = pillar["model"]
        prompts = pillar["prompts"]

        ans = query_model(model, title, prompts)
        results[p_id] = {
            "title": title,
            "model": model,
            "prompts": prompts,
            "research": ans
        }
        time.sleep(1) # respectful pause between model calls

    out_file = Path("D:/GNW/perplexity-browser-api/production_100_research_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n=======================================================")
    print(f"100-PROMPT DEEP RESEARCH COMPLETED SUCCESSFULLY!")
    print(f"Results saved to: {out_file}")
    print(f"=======================================================")

if __name__ == "__main__":
    main()
