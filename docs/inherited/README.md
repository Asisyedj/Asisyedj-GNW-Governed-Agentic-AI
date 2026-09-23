# GNW Governed Agent

A deployable MVP of the GNW governed multi-agent workspace. It provides a conversational task surface, five specialist roles, fail-closed governance gates, approval queue language, and a machine-readable health endpoint.

## Run

```bash
python3 -m http.server 8080
```

Open `http://localhost:8080`. The production deployment is managed by Vercel.

## Safety boundary

This MVP is a governed interaction shell. It does not claim live provider execution, real identity integration, or video generation. External side effects remain proposals until a reviewer approves them. `/api/health` reports deployment readiness.
