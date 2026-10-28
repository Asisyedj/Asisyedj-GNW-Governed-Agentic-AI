# GNW Perplexity Bridge Governance Rules

- Always verify bridge health via `perplexity_bridge_health` before dispatching multi-model consensus swarms.
- Prioritize high-assurance reasoning models (`claude37sonnetthinking`, `gpt-5.6-sol-thinking`, `grok-4.7-thinking`) for architectural and security validation.
- Enforce strict memory zeroization and DPAPI secrets hygiene: never persist or log raw bearer tokens or authorization headers.
