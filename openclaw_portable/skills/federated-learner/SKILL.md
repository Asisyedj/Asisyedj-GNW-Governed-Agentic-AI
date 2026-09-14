---
name: federated-learner
description: Use when asked about privacy-preserving machine learning, federated learning across multiple agents/devices/organizations, training models without sharing raw data, differential privacy, or secure aggregation. Trigger phrases: 'federated learning', 'train without sharing data', 'privacy-preserving ML', 'differential privacy', 'multi-party model training'. Enterprise-grade: DP budgets, Byzantine-robust aggregation, audit trails.
---

# Cross-Instance Federated Learner (OC-049)

Privacy-preserving federated learning across multiple agent instances. Train models collaboratively without sharing raw data.

## Features

- **Secure Aggregation**: Shamir Secret Sharing for model updates
- **Differential Privacy**: ε-δ budget tracking per participant
- **Byzantine Robustness**: TrimmedMean aggregation against malicious actors
- **Async Support**: Handle stragglers and dropouts gracefully
- **Governance**: Participant registry, consent tracking, audit logs
- **Model Versioning**: Track global model lineage

## Architecture

```
federated_learner/
├── coordinator/
│   ├── server.py           # gRPC coordination server
│   ├── aggregator.py       # Secure aggregation (Shamir SS)
│   ├── dp_accountant.py    # Differential privacy budget
│   └── scheduler.py        # Round scheduling
├── participant/
│   ├── client.py           # Participant client
│   ├── local_trainer.py    # Local model training
│   ├── privacy_filter.py   # Local DP noise addition
│   └── secure_channel.py   # TLS + certificate pinning
├── protocols/
│   ├── shamir_ss.py        # Shamir Secret Sharing
│   ├── trimmed_mean.py     # Byzantine-robust aggregation
│   ├── secure_agg.py       # Secure aggregation protocol
│   └── key_exchange.py     # ECDH key exchange
├── models/
│   ├── registry.py         # Model registry
│   ├── versioning.py       # Model versioning
│   └── serialization.py    # Model serialization
├── governance/
│   ├── consent.py          # Consent management
│   ├── audit.py            # Audit trail
│   └── policy.py           # Privacy policy enforcement
└── cli.py                  # start | join | status | audit
```

## Privacy Guarantees

| Guarantee | Mechanism | Parameter |
|---|---|---|
| Data Privacy | Local training only | Raw data never leaves device |
| Update Privacy | Secure aggregation | Server sees only aggregate |
| Output Privacy | Differential privacy | ε=1.0, δ=1e-5 per round |
| Robustness | TrimmedMean | 20% Byzantine tolerance |

## Safety (7 Layers)

1. HITL Gates — approval before joining federation
2. Rate Limiting — max 10 rounds/hour
3. Context Anchoring — FEDERATION.md as root
4. Credential Encryption — ECDH key exchange
5. Circuit Breakers — auto-pause on failure
6. Input Sanitization — validate all updates
7. Compaction Safety — backup before aggregation

## Config

- min_participants: 3
- max_participants: 100
- rounds_per_day: 24
- dp_epsilon: 1.0
- dp_delta: 1e-5
- byzantine_tolerance: 0.2
- model_type: pytorch / tensorflow / sklearn
