"""
World No.1 Personal Agent: 100-vector Deep Research via the local Perplexity Bridge.
Uses bridge access key from DPAPI-backed secret store; never logs credentials.
Ten research batches, ten vectors each, plus evidence-bounded synthesis.
"""
import json, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from gnw_secrets import get_bridge_key

ROOT = Path(r"D:\GNW")
BRIDGE = "http://127.0.0.1:8000"
MODEL = "perplexity/deep-research"
SYNTHESIS_MODEL = "perplexity/best"
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
STEM = f"world_no1_agent_research_100_{STAMP}"
JSONL_PATH = OUT / f"{STEM}.jsonl"
REPORT_PATH = OUT / f"{STEM}.md"
key = get_bridge_key()

PILLARS = [
("P1", "Future direction, industry signals, competitive architecture", [
"1.1 From current AI-company job postings, official product roadmaps, and engineering publications, what capabilities receive durable investment through 2026-2030? Distinguish hiring evidence from marketing.",
"1.2 Which architecture layers are converging around personal agents: models, runtimes, tool use, memory, connectors, identity, evaluation, policy, and observability?",
"1.3 What defensible advantage can an independent personal-agent product build against OpenAI, Google, Microsoft, AWS, Anthropic, NVIDIA, Meta, Mistral, Cohere and xAI?",
"1.4 Compare open-weight, closed-hosted, local and hybrid models for personal agents: quality, privacy, cost, latency, control, maintenance and lock-in.",
"1.5 What do current hardware, inference and model-efficiency developments imply for affordable always-on agents?",
"1.6 What has demonstrably improved in computer-use/browser agents, and what reliability and security limits remain?",
"1.7 What evidence supports or challenges multi-agent systems over a single orchestrator with specialist tools?",
"1.8 Which privacy, consent and local-first patterns could become essential for personal agents?",
"1.9 Which widely marketed agent capabilities fail in real deployments, and what published evidence identifies causes?",
"1.10 Construct evidence-backed 2030 and 2036 scenarios for personal agents; include uncertainties, triggers and falsifiable indicators."
]),
("P2", "Long-horizon planning, execution, recovery and state", [
"2.1 Compare current benchmarks for long-horizon agent tasks; do they measure real completion or short demonstrations?",
"2.2 What hierarchical planning and task decomposition methods improve performance on projects spanning many steps or days?",
"2.3 Which persistent state, checkpoint and event-sourcing designs best preserve task intent, intermediate artifacts, constraints and next actions?",
"2.4 How should agents recover after tool failure, process restart, context loss, partial completion or contradictory tool results?",
"2.5 What concurrency and dependency-control methods prevent duplicate work, races and conflicting writes across subagents?",
"2.6 Compare context windows, summarization, retrieval and external state for managing context degradation over long tasks.",
"2.7 How should an agent distinguish durable user goal, current plan, evidence, assumptions, blockers and stale state?",
"2.8 What techniques verify that an external task truly completed instead of trusting the model's claim?",
"2.9 How should the system handle user interruptions, changed priorities, cancellation, deadlines and delegated work safely?",
"2.10 Recommend benchmarks and pass/fail metrics for long-running personal-agent execution and recovery."
]),
("P3", "Long-term memory, personalization and user control", [
"3.1 Compare memory schemas for facts, preferences, decisions, project state, episodic history and learned skills.",
"3.2 What consent UX and controls make memory inspectable, correctable, scoped, exportable and deletable?",
"3.3 How can memory recall precision, recall, relevance, freshness and user correction burden be measured?",
"3.4 Compare memory consolidation, summarization, decay and forgetting; identify risks of irreversible compression.",
"3.5 Compare SQL/document stores, vector search, knowledge graphs and hybrid retrieval for personal memory.",
"3.6 When does RAG over personal files outperform stored summaries, and how should provenance be retained?",
"3.7 Which local-first and encrypted memory architectures are practical across desktop, cloud and mobile?",
"3.8 How should contradictory, stale, uncertain and source-conflicting memories be represented and resolved?",
"3.9 What consistency and conflict-resolution methods work for a personal agent syncing across devices?",
"3.10 Design a production evaluation plan for personalization without rewarding invasive collection or overconfident assumptions."
]),
("P4", "Tool use, connectors, MCP, browser and execution semantics", [
"4.1 What does current evidence indicate about MCP adoption, security model, conformance and interoperability gaps?",
"4.2 Compare direct API adapters, MCP servers, workflow engines and browser automation for tool integration.",
"4.3 What provenance and permission metadata should every tool, connector and returned artifact carry?",
"4.4 How should a connector SDK validate input/output schemas, version compatibility, scopes and tenant boundaries?",
"4.5 When is computer use genuinely needed instead of a stable API, and how should the system choose safely?",
"4.6 Which idempotency keys, transaction patterns and postcondition checks prevent duplicate or partial external actions?",
"4.7 Recommend timeout, retry, exponential backoff, rate-limit and circuit-breaker defaults for agent tools.",
"4.8 Which typed contracts and structured-output checks materially reduce tool-call errors?",
"4.9 What safeguards are needed for files, code execution, browser, email, calendar, ticketing and database tools?",
"4.10 Which connector capabilities should be open standards versus vendor-specific, and how can portability be tested?"
]),
("P5", "Trust, safety, identity, permissions and adversarial robustness", [
"5.1 Summarize current research and mitigations for direct and indirect prompt injection in tool-using agents.",
"5.2 How should human approval bind to exact action, target, parameters, scope, expiry and context to prevent bypass?",
"5.3 Design identity binding across human user, agent, subagent, tenant, session and tool workload.",
"5.4 Compare least-privilege delegation, short-lived credentials, token exchange and capability-based authorization.",
"5.5 What must an append-only, replayable audit trail record without leaking secrets?",
"5.6 Compare policy-as-code engines and enforcement points; where should allow/deny decisions be made?",
"5.7 How can approvals be triggered by risk and uncertainty without making routine automation unusably slow?",
"5.8 Compare OS sandboxing, containers, microVMs and remote isolated execution for untrusted agent actions.",
"5.9 What are current best practices for secret management, log redaction, rotation and revocation?",
"5.10 Propose a red-team suite covering prompt injection, confused deputy, scope escalation, data exfiltration, replay and approval bypass."
]),
("P6", "Evaluation, reliability, evidence and continuous verification", [
"6.1 Compare offline benchmarks, online evaluation, shadow mode, canary deployment and human review for agents.",
"6.2 Define an honest task-success metric with denominator, partial completion, external-effect verification and retries.",
"6.3 Which benchmark design choices make personal-agent results reproducible, representative and resistant to leakage?",
"6.4 How should uncertainty be calibrated and routed to a human, alternate model or safe fallback?",
"6.5 What evidence/provenance should accompany web research claims, including source date, authority and contradictions?",
"6.6 How can tool observations be grounded and cross-checked instead of accepting hallucinated results?",
"6.7 Design regression tests for model/provider upgrades, prompt changes, connector versions and memory changes.",
"6.8 When are synthetic tasks useful, and how should they be supplemented with anonymized real tasks?",
"6.9 How should user corrections, overrides and incidents feed into evaluation without silently changing policy?",
"6.10 Create an incident taxonomy and dashboard covering safety, quality, cost, latency and user impact."
]),
("P7", "Cost, speed, compute and energy efficiency", [
"7.1 Design model routing by task complexity, sensitivity, latency budget, evidence requirements and expected success.",
"7.2 Which caching methods are safe for prompts, retrieval, tool results and intermediate plans when permissions may change?",
"7.3 How can context/token use be reduced without losing critical constraints, citations or task state?",
"7.4 Compare local inference, hosted APIs and hybrid execution for typical personal-agent workloads.",
"7.5 Which measurements best expose tail latency (p50/p95/p99) across model, tool, queue and approval stages?",
"7.6 When is parallel tool execution safe, and how should dependencies and rate limits constrain concurrency?",
"7.7 How should a global retry budget prevent loops, runaway costs and repeated writes?",
"7.8 Define cost per verified successful task and compare it with token cost or agent-session cost.",
"7.9 What current hardware/model trends affect energy per inference and always-on assistant economics?",
"7.10 Develop a cost-and-latency budget for an MVP with explicit assumptions and thresholds to route, defer or stop."
]),
("P8", "Privacy, enterprise governance, deployment and compliance", [
"8.1 Compare data-residency and privacy trade-offs among hosted SaaS, customer VPC, on-premises and local deployment.",
"8.2 What controls prevent cross-tenant memory, retrieval, tool-result and audit-log leakage?",
"8.3 Compare encryption at rest/in transit, key ownership, customer-managed keys and memory-field encryption.",
"8.4 How should consent withdrawal, retention expiry, deletion, export and backups interact in long-term memory?",
"8.5 What enterprise identity integration is required: SSO, RBAC/ABAC, SCIM, workload identity and delegated credentials?",
"8.6 Which current NIST, OWASP, ISO, SOC 2 or other frameworks are relevant, and what is guidance versus certification?",
"8.7 What agent registry, owner, version, purpose and permission inventory should enterprise administrators have?",
"8.8 When do regulated customers require VPC/private/on-prem deployment, and how can the product validate demand?",
"8.9 How should connector scopes enforce data minimization and record-level authorization?",
"8.10 Define an enterprise incident-response and evidence package for a compromised or misbehaving agent."
]),
("P9", "Architecture review and migration strategy for World No.1 Personal Agent", [
"9.1 Compare a general agent framework with a model-neutral Agent Trust & Execution Plane; identify overlap and gaps.",
"9.2 Prioritize a narrow MVP for a prototype whose planner/tool selection and memory are basic and whose approval enforcement requires verification.",
"9.3 Propose a reference architecture for planner, durable task state, policy gateway, executor, connector SDK, memory and evaluation.",
"9.4 How should approval enforcement be made server-side and impossible to bypass through alternate code paths?",
"9.5 How can JSON-index/preview-based memory evolve toward provenance-rich retrieval without premature complexity?",
"9.6 Which tests are essential before write-capable tools are enabled, and what evidence proves each control?",
"9.7 How should a prototype migrate incrementally without rewriting everything or claiming unimplemented integrations?",
"9.8 Recommend telemetry and traces to reconstruct each decision, tool call, approval, retry and external effect.",
"9.9 Compare build-versus-buy for identity, policy engines, sandboxing, observability and connector infrastructure.",
"9.10 Produce a staged architecture-hardening order based on exploitability, blast radius, user value and verification cost."
]),
("P10", "Product, market, moat, roadmap and strategic decisions", [
"10.1 Which initial workflow niches most need a trusted personal/enterprise agent and have measurable repeatable value?",
"10.2 Map competitors for agent runtimes, control planes, identity, evaluation and personal memory.",
"10.3 Explain the risk that hyperscalers bundle governance/control-plane features and make independent products redundant.",
"10.4 What differentiators are hardest to copy: portable audit evidence, risk policy, cross-vendor integration or customer-controlled deployment?",
"10.5 Design an ROI experiment comparing an agent with a human/current workflow using success, time, error and review cost.",
"10.6 Compare pricing by protected agent, user/tenant, execution volume, protected workflow and enterprise deployment.",
"10.7 How can a small team recruit design partners and earn trust before certifications or a large installed base?",
"10.8 Evaluate open-source core, managed SaaS, private deployment and hybrid business models for trust infrastructure.",
"10.9 Give scenario-based 1-, 3-, 5- and 10-year roadmaps, with stop/pivot gates and conditions that invalidate the thesis.",
"10.10 Rank the next 20 engineering/research tasks for World No.1 Personal Agent by impact, evidence strength, risk reduction and dependency."
])
]

CONTEXT = """Project context supplied by the user (verify rather than blindly assume):
- A dated official AI-company career-posting sample across Google/DeepMind, AWS, NVIDIA, OpenAI, Anthropic, Microsoft, Meta, Mistral, Cohere and xAI indicates investment across training/post-training/RL, evaluation/safety, inference/GPU infrastructure, tool-using agents and production deployment.
- A strategy report proposes a model-neutral Agent Trust & Execution Plane: agent registry, user/agent identity, least privilege, policy gateway, action-specific approvals, isolated execution, replayable audit, observability/evaluation and limited connectors.
- Prior project discussion raised prototype risks to audit against actual code: keyword-based planning, hardcoded tool selection, basic JSON/index/preview memory, uncertain central approval enforcement, and integrations described without corresponding adapters. Do not assume they are fixed or claim any feature without evidence.
- The goal is a useful, safe, long-running personal agent, not a slogan about being number one."""

def get_json(path, timeout=20):
    req = urllib.request.Request(BRIDGE + path, headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def call_model(model, prompt, timeout=300):
    payload = {"model": model, "messages": [
        {"role":"system","content":"You are an evidence-first AI systems researcher. Use live web research where available, cite direct source URLs and publication/update dates, and never invent citations or present inference as sourced fact."},
        {"role":"user","content":prompt}], "max_tokens":3500, "stream":False}
    req = urllib.request.Request(BRIDGE + "/v1/chat/completions",
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type":"application/json","Authorization":"Bearer "+key},method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("bridge returned no choices")
    content = choices[0].get("message",{}).get("content","")
    if not isinstance(content,str) or not content.strip():
        raise RuntimeError("bridge returned empty content")
    return content

def main():
    print("PREFLIGHT checking bridge health and advertised model...")
    health = get_json("/v1/health")
    models = get_json("/v1/models")
    ids = {m.get("id") for m in models.get("data",[])}
    if MODEL not in ids:
        raise RuntimeError("perplexity/deep-research absent from live model list")
    print(f"PREFLIGHT_PASS health={health.get('status','unknown')} live_models={len(ids)} model={MODEL}")
    rows = []
    for idx,(pid,title,questions) in enumerate(PILLARS,1):
        prompt = f"""{CONTEXT}

Research date: 2026-10-25. Workstream {pid}: {title}. This batch contains 10 separately numbered research vectors (100 total across all batches).

Method:
1. Use current web research, not memory only. Prioritize original sources: official technical/security documentation, primary research, standards bodies, credible independent evaluations and current job postings. Seek multiple useful sources per vector where feasible.
2. Answer every vector in order. For each provide findings, direct Markdown citations with publisher and date, implications for World No.1 Personal Agent, a concrete experiment/design decision, confidence and unresolved uncertainty.
3. Label FACT, INFERENCE and RECOMMENDATION. Identify contradictions and vendor claims lacking independent validation.
4. Do not invent titles, scores, prices, laws, sources or citations. If reliable current evidence is unavailable, say so.
5. Focus on implementation choices, failure modes, testable architecture and business implications. Do not claim prototype features are implemented without code evidence.
6. End with the five most important decisions/tests and a compact source ledger.

TEN RESEARCH VECTORS
{chr(10).join('- '+q for q in questions)}

Write a substantive technical report; keep every exact vector number visible and retain source URLs."""
        print(f"\n[{idx:02d}/10] START {pid} {title}; vectors={len(questions)}",flush=True)
        started = time.time()
        row = {"type":"research_batch","pillar_id":pid,"title":title,"model":MODEL,
               "question_count":len(questions),"questions":questions,"started_utc":datetime.now(timezone.utc).isoformat()}
        try:
            probe_path = OUT / "world_no1_p1_probe_20261025.txt"
            if idx == 1 and probe_path.is_file():
                content = probe_path.read_text(encoding="utf-8")
                if len(content) < 10000:
                    raise RuntimeError("completed P1 probe output is unexpectedly short")
                row["reuse_source"] = str(probe_path)
            else:
                content = call_model(MODEL,prompt)
            row.update({"status":"PASS","elapsed_seconds":round(time.time()-started,1),"response_chars":len(content),"research":content})
            print(f"[{idx:02d}/10] PASS {pid} seconds={row['elapsed_seconds']} chars={len(content)}",flush=True)
        except Exception as exc:
            row.update({"status":"FAIL","elapsed_seconds":round(time.time()-started,1),"error_type":type(exc).__name__,"error":str(exc)[:300],"research":""})
            print(f"[{idx:02d}/10] FAIL {pid} {type(exc).__name__}: {str(exc)[:160]}",flush=True)
        with JSONL_PATH.open("a",encoding="utf-8") as f:
            f.write(json.dumps(row,ensure_ascii=False)+"\n")
        rows.append(row)
        time.sleep(1.5)

    good = [r for r in rows if r["status"]=="PASS"]
    synthesis = ""
    if good:
        excerpts = "\n\n".join("## "+r["pillar_id"]+" — "+r["title"]+"\n"+r["research"][:2500] for r in good)
        synthesis_prompt = f"""{CONTEXT}

Synthesize these Perplexity Bridge reports from 2026-10-25. Do not claim failed or missing vectors were completed. Preserve cited URLs as provided; never invent citations. Flag claims with only single-source or vendor-only support.

Deliver:
1. Executive decision: what should be built and what should not be built yet?
2. Ten strongest cross-batch findings with evidence and confidence.
3. Reference architecture and trust boundaries.
4. Prioritized 0-90 day plan with concrete artifacts, tests and pass/fail gates.
5. One-, three-, five- and ten-year scenarios and thesis-falsification/stop conditions.
6. Top 15 technical risks and mitigations.
7. Benchmark/ROI plan for safety, verified task success, latency, cost per successful task and user correction.
8. Contradictions, source gaps and research debt.
9. Ranked top-20 backlog with dependency, impact, risk, evidence and priority.
10. Final table: BUILD NOW / VERIFY FIRST / DEFER / DO NOT BUILD.
Separate sourced facts, report-based claims, inference and recommendations.

REPORT EXCERPTS
{excerpts}"""
        print("\n[11/11] START synthesis",flush=True)
        st=time.time()
        try:
            synthesis=call_model(SYNTHESIS_MODEL,synthesis_prompt)
            syn={"type":"synthesis","model":SYNTHESIS_MODEL,"status":"PASS","elapsed_seconds":round(time.time()-st,1),"response_chars":len(synthesis),"research":synthesis}
            print(f"[11/11] PASS synthesis chars={len(synthesis)}",flush=True)
        except Exception as exc:
            syn={"type":"synthesis","model":SYNTHESIS_MODEL,"status":"FAIL","error_type":type(exc).__name__,"error":str(exc)[:300],"research":""}
            print(f"[11/11] FAIL synthesis {type(exc).__name__}: {str(exc)[:160]}",flush=True)
        with JSONL_PATH.open("a",encoding="utf-8") as f:
            f.write(json.dumps(syn,ensure_ascii=False)+"\n")
    else:
        syn={"type":"synthesis","status":"NOT_RUN","research":""}

    done_vectors=sum(r["question_count"] for r in good)
    lines=["# World No.1 Personal Agent — 100-Vector Deep Research","",
        f"- Run UTC: {STAMP}",f"- Bridge: {BRIDGE}",f"- Research model: {MODEL}",
        "- Research vectors requested: 100",
        f"- Successful research batches: {len(good)}/10",
        f"- Vectors in successful batches: {done_vectors}/100",
        f"- Failed batches: {len(rows)-len(good)}",
        f"- Synthesis status: {syn.get('status','NOT_RUN')}",
        "- Execution scope: 100 vectors were organized in 10 separately numbered deep-research requests; this report does not misrepresent them as 100 independent API calls.",
        f"- Machine-readable log: {JSONL_PATH}","",
        "## Batch status","","| ID | Workstream | Vectors | Status | Seconds | Response chars |","|---|---|---:|---|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['pillar_id']} | {r['title']} | {r['question_count']} | {r['status']} | {r.get('elapsed_seconds','—')} | {r.get('response_chars',0)} |")
    for r in rows:
        lines += ["",f"## {r['pillar_id']} — {r['title']}","",r["research"] if r["status"]=="PASS" else f"FAILED: {r.get('error_type','Error')}: {r.get('error','no detail')}"]
    lines += ["","## Cross-batch synthesis","",synthesis if synthesis else "Synthesis unavailable; use the successful source-cited batch reports above."]
    REPORT_PATH.write_text("\n".join(lines),encoding="utf-8")
    summary={"run_utc":STAMP,"bridge":BRIDGE,"research_model":MODEL,"requested_vectors":100,
        "successful_batches":len(good),"vectors_in_successful_batches":done_vectors,
        "failed_batches":len(rows)-len(good),"batch_api_calls_attempted":len(rows),
        "synthesis_status":syn.get("status"),"jsonl_path":str(JSONL_PATH),"markdown_report_path":str(REPORT_PATH),
        "batch_status":[{"pillar_id":r["pillar_id"],"title":r["title"],"status":r["status"],
            "question_count":r["question_count"],"elapsed_seconds":r.get("elapsed_seconds"),
            "response_chars":r.get("response_chars",0),"error":r.get("error")} for r in rows]}
    summary_path=OUT/f"{STEM}_summary.json"
    summary_path.write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print("\nFINAL_SUMMARY\n"+json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    print("REPORT_MD="+str(REPORT_PATH),flush=True)
    print("RESULTS_JSONL="+str(JSONL_PATH),flush=True)
    print("SUMMARY_JSON="+str(summary_path),flush=True)
    if len(good)!=10 or syn.get("status")!="PASS":
        raise SystemExit(2)

if __name__=="__main__":
    main()
