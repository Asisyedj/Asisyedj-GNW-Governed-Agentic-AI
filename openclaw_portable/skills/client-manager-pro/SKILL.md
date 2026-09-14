---
name: client-manager-pro
description: Use when asked to manage clients, automate client communication, send or schedule follow-up messages, handle client onboarding, or run outreach across Slack, email, or WhatsApp. Trigger phrases: 'manage my clients', 'send follow-up', 'client communication', 'schedule a message to my client', 'client CRM', 'outreach to leads'. Enterprise-grade: human-in-the-loop approval before any send, rate limiting, templates, audit logging, disaster recovery.
---

# Client-Manager-Pro (OC-001)

Automate client communication across Slack, Email, and WhatsApp with intelligent scheduling, template management, follow-up reminders, and disaster recovery.

## Features

- **Multi-Channel**: Slack, Email (SMTP), WhatsApp (via Twilio)
- **Smart Templates**: Variable substitution, conditional content, A/B testing
- **Scheduling**: Timezone-aware, business-hours only, follow-up sequences
- **CRM Integration**: Notion, Airtable, custom webhooks
- **Analytics**: Open rates, response times, conversion tracking
- **Disaster Recovery**: Circuit breakers, fallback channels, HITL escalation

## Architecture

```
client_manager/
├── channels/
│   ├── slack.py          # Slack Web API + Socket Mode
│   ├── email.py          # SMTP + MIME templates
│   └── whatsapp.py       # Twilio WhatsApp API
├── templates/
│   ├── engine.py         # Jinja2 template engine
│   ├── library.py        # Template storage + versioning
│   └── variables.py      # Variable extraction + validation
├── scheduler/
│   ├── engine.py         # APScheduler integration
│   ├── sequences.py      # Follow-up sequences
│   └── timezone.py       # Timezone handling
├── crm/
│   ├── notion.py         # Notion database sync
│   ├── airtable.py       # Airtable integration
│   └── webhook.py        # Generic webhook handler
├── analytics/
│   ├── tracker.py        # Event tracking
│   ├── reports.py        # Report generation
│   └── dashboard.py      # Dashboard data
├── safety/
│   ├── rate_limiter.py   # Per-channel rate limiting
│   ├── circuit_breaker.py # Failure protection
│   └── approval.py       # HITL approval workflow
└── cli.py                # send | schedule | template | report | audit
```

## Safety (7 Layers)

1. HITL Gates — approval before bulk sends
2. Rate Limiting — 50 msgs/hour per channel
3. Context Anchoring — CLIENTS.md as root
4. Credential Encryption — AES-256-GCM
5. Circuit Breakers — auto-disable on failures
6. Input Sanitization — validate all inputs
7. Compaction Safety — backup before bulk ops

## Config

- default_channel: email
- business_hours: 9:00-18:00
- timezone: Asia/Karachi
- max_daily_messages: 200
- follow_up_delays: [24, 72, 168] (hours)
- approval_required: bulk_send, new_template, schedule_change
