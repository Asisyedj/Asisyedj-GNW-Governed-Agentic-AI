---
name: organization-memory-architect
description: Use when asked to remember things across sessions, build a persistent knowledge base or organizational memory, maintain a MEMORY.md, compact long context, or audit what an agent knows. Trigger phrases: 'remember this', 'organizational memory', 'knowledge base for my team', 'memory system', 'what do you remember'. Implements 5-tier storage, atomic writes, secret scanning, scope isolation, staleness detection.
---

# Organization Memory Architect (OC-048)

Persistent, compact, searchable organizational memory system that captures, compacts, retrieves, and audits institutional knowledge across agent sessions. Implements the MEMORY.md pattern with 5-tier storage, atomic writes, secret scanning, scope isolation, and staleness detection.

## Architecture

```
memory_architect/
├── core/       capture, retrieval, compaction, summarizer, indexer, staleness
├── models/     Pydantic v2: MemoryEntry, SearchResult, HealthReport
├── storage/    Atomic file I/O + backup rotation
├── security/   SecretScanner (10+ patterns), ScopeGuard (personal/team/org)
├── search/     keyword_search (weighted) + semantic_search (TF-IDF cosine)
└── cli.py      capture | retrieve | compact | summarize | index | audit
```

## Safety (7 Layers)

1. HITL Gates — approval before compaction
2. Rate Limiting — 100/hour
3. Context Anchoring — MEMORY.md root
4. Credential Encryption — AES-256-GCM
5. Circuit Breakers — auto-disable on failures
6. Input Sanitization — validate all keys/values
7. Compaction Safety — backup before compact
