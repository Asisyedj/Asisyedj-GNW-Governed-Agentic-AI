# GNW 1000 تحقیقی سوالات — بیچ 1: جامع اور تفصیلی جوابات (سوال 1 تا 200)

> **نوٹ:** یہ جوابات live web search، distributed systems کی real-world practices، اور verified architectural principles پر مبنی ہیں۔ ہر جواب میں step-by-step reasoning اور trade-offs شامل ہیں۔

---

## Control Plane (سوال 1 تا 70)

### Policy Gateway (سوال 1–10)

---

**سوال 1: Policy Gateway کا بنیادی ڈیزائن**

**Step-by-step ڈیزائن decisions:**

**(a) Synchronous vs Asynchronous:**
- **فیصلہ:** Hybrid model — tool call کا policy evaluation synchronous رکھیں، لیکن policy deployment/admin operations asynchronous ہوں۔
- **تفصیل:** Tool call کے وقت agent blocking ہے — اس لیے policy check اس کے execution path میں ہے۔ اگر asynchronous کریں تو agent کو نہیں پتہ کہ allow ہوا یا deny۔ اس لیے evaluation **synchronous** ہونا چاہیے (inline check)۔ لیکن policy updates، cache refresh، audit logging یہ **asynchronous** ہوں (fire-and-forget یا background worker)۔
- **Trade-off:** Synchronous evaluation = deterministic behavior، مگر latency overhead۔ Asynchronous = no blocking مگر eventual consistency کا مسئلہ۔
- **Verified principle:** OPA (Open Policy Agent) کا model بھی یہی ہے — policy decision synchronous (query-time) ہے، policy deployment/admin separate ہے۔ OPA کا official design یہی کہتا ہے: "Applications send a query to OPA, OPA evaluates synchronously, returns a decision."

**(b) Latency Budget:**
- **فیصلہ:** p99 latency budget = **≤5ms** (cached)، ≤15ms (cache miss)۔
- **تفصیل:** Agent کے tool call path میں policy check ایک حصہ ہے۔ اگر یہ 50ms لے تو agent的整体 UX خراب ہوگا۔ 5ms cached hit اور 15ms miss قابل قبول ہیں۔
- **Reasoning:** اگر 10,000 agents ہر سیکنڈ 5 calls کر رہے ہیں (50,000 evals/sec)، تو ہر evaluation میں 5ms = 250 concurrent evaluations needed۔ ایک modern CPU core ~10,000 simple policy evaluations/sec کر سکتا ہے، تو 25-30 cores کافی ہیں۔

**(c) Fail-open vs Fail-closed:**
- **فیصلہ:** **Configurable per-tool** — default = fail-closed for destructive operations، fail-open for read-only operations۔
- **تفصیل:**
  - Read-only operations (web search, file read) → **fail-open** ( اگر Gateway down ہو تو انہیں allow کریں، کیونکہ no side effects)
  - Write/destructive operations (file delete, email send) → **fail-closed** (deny کر دیں، کیونکہ unapproved side effects کا خطرہ)
- **Reasoning:** Pure fail-open = security bypass اگر Gateway down ہو۔ Pure fail-closed = availability disaster۔ Tool کے risk profile کے مطابق choose کریں۔

**(d) Policy Format:**
- **فیصلہ:** **OPA/Rego** کو primary format کے طور پر use کریں، Cedar کو evaluate کریں مگر ابھی Rego کو ترجیح دیں۔
- **Reasoning:**
  - **OPA/Rego:** CNCF graduated project، production-proven، JSON-native I/O، large ecosystem، Kubernetes integration، حقیقی production deployments میں استعمال ہو رہا ہے۔ Rego Datalog-based ہے جو declarative اور auditable ہے۔
  - **Cedar:** AWS کا ہے، relatively new، cleaner syntax مگر ecosystem چھوٹا ہے۔ Cedar کا advantage ہے کہ یہ more readable ہے مگر tooling کم ہے۔
  - **Custom DSL:** Avoid کریں — نئی language کا maintenance burden، testing، documentation، اور parsing security risks۔
- **Verified:** OPA کا official documentation اور CNCF status اسے سب سے زیادہ battle-tested option بناتا ہے۔

---

**سوال 2: Policy Evaluation کی ترتیب**

**Step-by-step evaluation order:**

1. **Authentication & Identity Check (پہلا check):**
   - کون agent ہے؟ کونسی tenant؟ کون سا user؟
   - **کیوں پہلے:** اگر identity ہی نہیں ہے تو باقی checks بے معنی ہیں۔ یہ سستے اور fast ہیں (JWT validation ~0.1ms)۔

2. **Rate Limit / Budget Check (دوسرا):**
   - کیا agent کا budget باقی ہے؟ کیا rate limit exhausted ہے؟
   - **کیوں:** اگر budget نہیں ہے تو باقی expensive policy evaluations waste ہیں۔ یہ بھی fast ہے (counter lookup)۔

3. **Tool-level Policy (تیسرا):**
   - کیا اس tool کا استعمال اس tenant/user کے لیے allowed ہے؟
   - **کیوں:** Coarse-grained deny سب سے پہلے — اگر tool ہی allowed نہیں تو attribute checks waste ہیں۔

4. **Attribute-based Policy (چوتھا):**
   - Runtime attributes: کون سا URL؟ کونسی file path؟ email recipient domain؟ SQL query type؟
   - **کیوں:** یہ سب سے expensive check ہے (data fetch + complex evaluation)۔ اسے صرف تب کرنا جب پچھلے checks pass ہوں۔

5. **Approval Check (آخری):**
   - کیا اس operation کے لیے human approval pending ہے یا needed ہے؟
   - **کیوں:** Approval asynchronous ہوتی ہے — اگر پہلے چیک کریں تو باقی evaluations waste ہوں گی جب approval pending ہو۔

**Short-circuit logic:**
- **ہاں، short-circuit کریں۔** اگر کوئی بھی check fail ہو تو باقی evaluate نہ کریں۔
- **Exception:** Audit logging کے لیے یہ log کرنا چاہیے کون سا check fail ہوا، باقی results نہیں چاہیے۔
- **Reasoning:** اگر browser check fail ہو تو email sender کی policy evaluate کرنا computation waste ہے۔ مگر audit میں یہ record ہونا چاہیے کہ "browser access denied" — باقی tools کا result "not evaluated" ہے۔

---

**سوال 3: Policy Conflict Resolution**

**Step-by-step strategy:**

**Approach: Specificity-based + Priority-based hybrid**

1. **Specificity-based resolution (primary):**
   - زیادہ specific policy کم specific policy پر override کرے گی۔
   - "All file writes need approval" = generic (low specificity)
   - "Backup files skip approval" = specific (high specificity)
   - **کیوں:** Specific policies intentional exceptions ہیں generic policies کے۔ یہ قانونی reasoning کا standard principle ہے۔

2. **Priority-based (secondary):**
   - اگر دونوں policies ایک ہی specificity level پر ہیں تو explicit priority field کا استعمال۔
   - `priority: 100` > `priority: 50`
   - **کیوں:** کبھی explicit priority ضروری ہے جب specificity sama ہو۔

3. **Timestamp-based (NOT recommended as primary):**
   - صرف fallback کے طور پر — اگر specificity اور priority دونوں same ہوں تو newer policy wins۔
   - **کیوں نہیں:** Timestamp-based resolution unpredictable ہے — deploy order behavior کو change کر سکتا ہے۔

**Edge cases:**
- **Partial overlap:** Policy-A کہتی ہے "file writes need approval"، Policy-B کہتی ہے "backup files in /tmp/ skip approval"۔ اگر file `/tmp/backup_2024.txt` ہے تو Policy-B wins (زیادہ specific)۔ اگر file `/home/user/doc.txt` ہے تو صرف Policy-A applies (Policy-B کا scope match نہیں)۔
- **Contradictory same-level:** دو policies ایک ہی level پر، ایک allow، ایک deny → **default deny** (security principle: when in doubt, deny)۔
- **Temporal conflicts:** Time-bound policy (e.g., "no writes during business hours") vs always-on policy → time-bound زیادہ specific ہے۔

---

**سوال 4: Policy Hot-Reloading**

**Step-by-step implementation:**

**(a) In-flight requests:**
- **Strategy:** **Version-stamped requests** — ہر policy evaluation request میں policy version ID embed کریں۔
- جب نئی policy deploy ہو:
  - Existing in-flight requests **purانے version** سے complete ہوں (چونکہ انہوں نے evaluation start کی تھی purانے version کے ساتھ)
  - New requests نئی version سے evaluate ہوں
- **Reasoning:** Mid-flight policy change کا مطلب inconsistent evaluation — half checks purانے policy سے، half نئے سے۔ یہ security hole ہے۔

**(b) Syntax error rollback:**
- **Strategy:** **Canary validation + atomic swap**
  1. نئی policy کو parse اور validate کریں (dry-run)
  2. اگر syntax error ہو تو deploy fail ہو جائے، purانی policy متاثر نہیں ہوتی
  3. اگر parse success مگر runtime error ہو (e.g., undefined variable) تو **automatic rollback** trigger ہو
  4. Rollback: previous version کو atomic swap سے restore کریں
- **Implementation:** Two-slot deployment — `active_version` اور `staging_version`۔ Canary deployment میں staging کو test کریں، success پر atomic swap۔

**(c) Policy versioning + audit trail:**
- **Strategy:** ہر policy کو immutable version ID دیں (e.g., `policy_v_2024_01_15_001`)۔
- Audit log میں ہر decision record میں: `decision_id`, `policy_version`, `timestamp`, `result`, `reasoning`۔
- کسی بھی historical decision کو replay کر سکیں: "اس وقت کون سی policy active تھی؟" → version ID سے retrieve کریں۔
- **Reasoning:** Compliance (SOC2, GDPR) requires knowing which policy was in effect when a decision was made۔

---

**سوال 5: Policy Gateway Performance at Scale (50,000 evals/sec)**

**Step-by-step strategy:**

**(a) Caching strategy:**
- **Cacheable:** Static policy decisions — `tenant_id + user_id + tool_name + static_attributes`۔ اگر policy صرف identity اور tool name پر depend کرتی ہے (no runtime attributes) تو decision 100% cacheable۔
- **Not cacheable:** Attribute-dependent decisions — اگر URL, file path, query parameters affect decision تو cache نہیں (ہر request الگ ہے)۔
- **Partially cacheable:** Policy rules themselves cache کریں (parsed AST)، مگر final decision per-request evaluate کریں۔

**(b) Cache invalidation:**
- **Event-driven:** Policy update publish ہو تو cache entries کو invalidate کریں (pub/sub message)۔
- **TTL-based:** ہر cached decision کا TTL = 60 seconds (safety net — اگر event-driven invalidation miss ہو)۔
- **Version-stamped:** Cache key میں policy version شامل ہو — نئی version = نئی cache namespace = automatic invalidation۔

**(c) Distributed cache consistency:**
- **Strategy:** Redis cluster یا similar distributed cache۔
- Write-through: ہر evaluation result کو cache میں لکھیں۔
- Invalidation broadcast: policy update ہو تو تمام cache nodes کو invalidate message بھیجیں۔
- **Eventual consistency window:** ~100ms (acceptable — stale cache 60s TTL سے بہتر ہے)۔

**(d) p99 latency calculation:**
- Cache hit ratio = 95%، miss latency = 5ms
- p50 = ~0.5ms (cache hit)
- p95 = ~5ms (cache miss, full evaluation)
- p99 = ~5ms + queueing delay ≈ **8-10ms**
- اگر p99 > 15ms ہو تو bottleneck ہے — need more Gateway instances یا better caching۔

---

**سوال 6: Multi-Tenant Policy Isolation**

**Step-by-step isolation strategy:**

1. **Tenant ID in every request context:**
   - ہر policy evaluation input میں `tenant_id` mandatory field ہے۔
   - Policy rules میں `tenant_id` سے scope کریں — Tenant-A کی rules میں Tenant-B کا کوئی reference نہیں۔

2. **Policy namespace isolation:**
   - OPA/Rego میں: `package tenant_a.authz` اور `package tenant_b.authz` — مکمل separation۔
   - Cross-tenant policy reference技术上 ممکن نہیں (Rego packages isolated ہیں)۔

3. **Data isolation:**
   - Policy evaluation میں fetch ہونے والے attributes بھی tenant-scoped ہوں۔
   - Attribute fetch queries میں `WHERE tenant_id = ?` mandatory ہے۔
   - اگر query میں tenant_id نہیں ہے تو query reject ہو۔

4. **Cache isolation:**
   - Cache key میں tenant_id شامل ہے: `cache_key = hash(tenant_id + user_id + tool_name + attributes)`
   - Tenant-A کا cached decision Tenant-B کے لیے قابل استعمال نہیں۔

5. **Audit isolation:**
   - Audit logs میں tenant_id field ہے۔
   - Cross-tenant audit queries denied (unless platform admin)۔

6. **Testing:**
   - Penetration test: Tenant-A کے context سے Tenant-B کا data access attempt کر کے verify کریں۔
   - Automated test: ہر deploy پر cross-tenant access test چلائیں۔

**Reasoning:** Multi-tenant isolation کی ناکامی سب سے بڑا breach vector ہے — یہ verified best practices ہیں (shared schema + tenant_id field + query-level filtering)۔

---

**سوال 7: Policy Composition (Platform + Tenant + User level)**

**Step-by-step composition for "email sentiment analysis report share" request:**

1. **Platform-level policy evaluation (پہلا):**
   - کیا email access platform کے لیے allowed ہے؟ (نعم / نہیں)
   - کیا email sending/receiving capability globally enabled ہے؟
   - اگر platform deny کرے → done، tenant/user policies evaluate نہیں۔

2. **Tenant-level policy evaluation (دوسرا):**
   - کیا اس tenant نے email access enable کیا ہے؟
   - کیا tenant کی policies "email sentiment analysis" allow کرتی ہیں؟
   - کیا tenant کے data residency rules email data sharing allow کرتے ہیں؟
   - اگر tenant deny کرے → done، user policy evaluate نہیں۔

3. **User-level policy evaluation (تیسرا):**
   - کیا اس user کو email access permission ہے؟
   - کیا user کے emails کا sentiment analysis allowed ہے؟
   - کیا "sharing" کا action allowed ہے — کس کے ساتھ share؟
   - کیا sentiment analysis report میں PII (personally identifiable information) ہو سکتی ہے؟ اگر ہاں تو masking required۔

4. **Composition logic:**
   - **Denial precedence:** اگر کوئی بھی level deny کرے → final decision = deny
   - **Allowance precedence:** تمام levels allow کریں → final decision = allow
   - **Additional constraints:** اگر allow ہے مگر user-level میں "masking required" constraint ہے اور tenant-level میں "retention 30 days" constraint ہے تو **دونوں constraints apply** (AND composition)۔

5. **Decision:**
   - Allow + masking + 30-day retention + audit log = final composed decision۔

**Reasoning:** Composition = AND logic for denial (most restrictive wins)، مگر constraints additive ہیں (سب کے constraints apply ہوتے ہیں)۔

---

**سوال 8: Policy Testing and Simulation (Shadow Mode)**

**Step-by-step shadow mode implementation:**

1. **Shadow evaluation setup:**
   - نئی policy کو `staging` mode میں deploy کریں۔
   - ہر live request کے لیے: purانی policy (active) سے evaluate کریں → یہی actual decision ہے۔
   - **Same request** نئی policy (shadow) سے evaluate کریں → یہ result **log only** ہے، apply نہیں ہوتا۔

2. **Comparison logging:**
   - ہر shadow evaluation کا result compare کریں: `active_result` vs `shadow_result`۔
   - اگر match ہے → no behavior change۔
   - اگر mismatch ہے → flag for review: "نئی policy اس request کے لیے different decision دی۔"

3. **Metrics collection:**
   - Match rate: %requests جہاں دونوں policies same decision دیں۔
   - Mismatch breakdown: کتنے میں shadow deny کرے جہاں active allow تھا؟ (over-restrictive)
   - کتنے میں shadow allow کرے جہاں active deny تھا؟ (under-restrictive — security concern)

4. **Promotion criteria:**
   - Shadow run 7 days یا 1M requests۔
   - Match rate ≥ 99.5% (acceptably low divergence)۔
   - Under-restrictive mismatches = 0 (security-critical)۔
   - اگر criteria met → promote shadow to active۔

5. **Rollback safety:**
   - اگر promotion کے بعد issues آئیں تو 1-click rollback to previous version۔

**Reasoning:** Shadow mode production behavior کو disturb کیے بغیر validation کرتا ہے۔ یہ Canary deployment کا policy equivalent ہے۔

---

**سوال 9: Policy Gateway Observability**

**Step-by-step observability stack:**

**Log fields (structured JSON):**
```
{
  "timestamp", "request_id", "tenant_id", "user_id", "agent_id",
  "tool_name", "operation_type", "policy_version",
  "decision": "allow|deny", "matched_rules": [...],
  "evaluation_time_ms", "cache_hit": true|false,
  "attributes": {...}, "reason": "..."
}
```

**Metrics:**
| Metric | Type | Description |
|---|---|---|
| `policy_evaluations_total` | Counter | Total evaluations (labels: tenant, tool, decision) |
| `policy_evaluation_latency` | Histogram | Latency distribution (p50, p95, p99) |
| `policy_cache_hit_ratio` | Gauge | Cache hit % |
| `policy_denials_total` | Counter | Denials by reason |
| `policy_version_active` | Gauge | Current active version |
| `policy_shadow_mismatches` | Counter | Shadow mode mismatches |
| `gateway_health` | Gauge | 1=healthy, 0=unhealthy |

**Alerting rules:**
- `policy_evaluation_latency_p99 > 15ms` → WARNING
- `policy_cache_hit_ratio < 80%` → WARNING (cache not effective)
- `policy_denials_total` spike > 3x baseline → WARNING (possible policy misconfiguration)
- `gateway_health == 0` → CRITICAL
- `policy_shadow_mismatches > 0.5%` → WARNING (shadow policy diverging)

**Tracing:**
- ہر policy evaluation کو distributed trace span کے طور پر record کریں۔
- Parent span = tool call، child span = policy evaluation۔
- یہ سے پتہ چلے گا کہ policy evaluation نے total latency میں کتنا contribute کیا۔

---

**سوال 10: Attribute-Based Policy Evaluation**

**Step-by-step attribute fetch strategy:**

1. **Attribute sources:**
   - **Identity attributes:** tenant_id, user_id, role, department → from JWT token (fast, cached)
   - **Resource attributes:** file path, email recipient, URL → from request payload (available)
   - **Contextual attributes:** time of day, IP address, device → from request metadata
   - **External attributes:** user's approval history, recent activity, risk score → from external services (slow, may fail)

2. **External dependency unavailable:**
   - **Strategy:** Configurable per-attribute fallback:
     - **Critical attributes (e.g., risk score for destructive ops):** fail-closed — if unavailable, deny
     - **Non-critical attributes (e.g., department for read-only):** fail-open — use default value
   - **Timeout:** 50ms max for external attribute fetch۔ اگر timeout ہو تو fallback apply ہو۔

3. **Stale attributes:**
   - **Strategy:** TTL-based staleness:
     - Fresh: fetched within last 60 seconds → use directly
     - Stale: fetched 60s-5min ago → use with `stale=true` flag، policies میں stale-aware rules
     - Very stale: > 5min → re-fetch
   - **Reasoning:** کچھ policies stale data accept کر سکتی ہیں (e.g., department rarely changes)، کچھ نہیں (e.g., recent activity)۔

4. **Attribute caching:**
   - Identity attributes: cache for JWT lifetime (~15 min)
   - Resource attributes: don't cache (per-request)
   - External attributes: cache 60s with refresh

---

### Approval System (سوال 11–20)

---

**سوال 11: Approval Workflow State Machine**

**States:**
```
REQUESTED → PENDING_REVIEW → APPROVED → EXECUTING → COMPLETED
                    ↓
              REJECTED → CLOSED
                    ↓
              EXPIRED → CLOSED
                    ↓
          ESCALATED → PENDING_REVIEW (higher level)
```

**Step-by-step flow:**

1. **REQUESTED:** Agent نے approval request کی۔ Request ID generate، context capture۔
2. **PENDING_REVIEW:** Approver کو notification بھیجا۔ Timer start (e.g., 2 hours)۔
3. اگر approver approve کرے → **APPROVED** → **EXECUTING** → **COMPLETED**
4. اگر approver reject کرے → **REJECTED** → **CLOSED**
5. اگر timer expire ہو → **ESCALATED** → secondary approver کو notify → back to **PENDING_REVIEW**
6. اگر secondary بھی expire → manager → break-glass

**Multiple approvers:**
- **Sequential:** Approver 1 → Approver 2 → execute (higher security)
- **Parallel:** دونوں approvers کو simultaneously notify، either one approves → execute (faster)
- **Quorum-based:** 3 approvers میں سے 2 needed (high-stakes operations)

**Resume mechanism:**
- Approval approved ہونے کے بعد اگر agent restart ہو تو:
  - Approval record persisted in durable store
  - Agent resume ہو تو approval status check کرے → if APPROVED, proceed with execution
  - If agent permanently down → approval expires after 24h

---

**سوال 12: Approval Triggers Thresholds**

**Risk score calculation:**
- ہر tool call کا risk score calculate کریں:
  - **Operation type weight:** Read=1, Write=5, Delete=10, External send=8
  - **Resource sensitivity:** Public data=1, Internal=3, Confidential=7, PII=10
  - **Volume:** Single item=1, Batch>10=3, Batch>100=5
  - **Context:** Business hours=1, Off-hours=2, Unknown location=4
- **Risk score** = operation_weight × sensitivity_weight × volume_factor × context_factor

**Threshold calibration:**
- Score < 10 → Auto-approve (no human needed)
- Score 10-30 → Single approver
- Score 30-60 → Two approvers (sequential)
- Score > 60 → Manager + break-glass option

**Drift detection:**
- Weekly: average risk scores کا trend monitor کریں
- اگر 80%+ requests auto-approve ہو رہے ہیں → thresholds too low، tighten
- اگر 50%+ requests need human approval → thresholds too high، loosen (approval fatigue)

---

**سوال 13: Approval Escalation Chains**

**Step-by-step escalation chain:**

1. **Primary approver** (timer: 2 hours)
   - Notification: email + push notification
   - اگر no response in 2h → escalate

2. **Secondary approver** (timer: 1 hour)
   - Person designated by primary (e.g., team lead)
   - اگر no response in 1h → escalate

3. **Manager** (timer: 30 min)
   - Department manager
   - اگر no response in 30 min → break-glass

4. **Break-glass** (timer: 15 min)
   - Auto-approve with elevated logging
   - Post-review mandatory (within 24h, manager reviews)

**Timer management:**
- Timers persistent (survive restart)
- Cancellable (approver responds before timeout → timer cancelled)
- Notification retry: 3 attempts with backoff

**State tracking:**
- Current escalation level
- Total elapsed time
- Notification delivery status (sent, delivered, read)

---

**سوال 14: Approval with Context**

**Required context fields:**
1. **Operation summary:** "Delete 15 files in /shared/reports/Q3/"
2. **Agent reasoning:** "User requested cleanup of Q3 reports per retention policy"
3. **Resource details:** File list with sizes, last modified dates
4. **Risk assessment:** Risk score + breakdown
5. **Reversibility:** "Irreversible" یا "Reversible via backup"
6. **Impact:** "15 files, ~500MB total, used by 3 team members"
7. **Alternatives:** "Archive instead of delete?"

**Context generation automation:**
- Agent سے structured request format مانگیں: action, resources, reason, alternatives
- Risk assessment auto-calculated
- Impact analysis: resource dependencies auto-fetched
- Reversibility: tool-level metadata (is this operation reversible?)

**Approver overload prevention:**
- **Batch approvals:** اگر 50 files delete ہو رہی ہیں تو ایک summary approval
- **Smart filtering:** Low-risk auto-approve، only high-risk human review
- **Delegation:** Approver چھٹی پر ہو تو auto-delegate
- **Dashboard:** Approver کو queue view، not individual notifications for each request

---

**سوال 15: Time-Bound Approvals**

**Implementation:**

1. **One-shot approval (default):**
   - Valid for single execution
   - After execution → approval consumed → must re-request for next operation
   - TTL: 5 minutes to execute after approval, else expires

2. **Recurring approval (configurable):**
   - Valid for N executions (e.g., "delete up to 5 files in /tmp/")
   - TTL: 1 hour
   - Counter-based: decrement after each execution

3. **Time-bound window:**
   - Approved for specific time window (e.g., "valid 9 AM - 5 PM today")
   - After window → expired

**Expiry on in-flight operations:**
- اگر approval expire ہو جائے جبکہ operation正在进行:
  - **Graceful completion:** اگر operation >50% done → let it finish
  - **Hard stop:** اگر <50% → abort with rollback
  - **Decision:** Configurable per tool type

**Renewal:**
- Expiry سے 5 min پہلے auto-renewal request (if recurring pattern detected)
- Renewal = lightweight check (not full re-approval if risk unchanged)

---

**سوال 16: Approval Audit Trail**

**Mandatory fields:**
```
- approval_id, request_id, agent_id, tenant_id
- approver_id, approval_level (primary/secondary/manager/break-glass)
- decision (approved/rejected/expired)
- timestamp (requested, reviewed, decided, executed)
- context_snapshot (full context at time of request)
- policy_version (which policy triggered the approval requirement)
- risk_score, risk_breakdown
- signature (cryptographic hash of record)
```

**Tamper-proof storage:**
- **Append-only log:** Records insert-only ہیں، update/delete impossible
- **Cryptographic chaining:** ہر record کا hash previous record کے hash پر depend کرتا ہے (like blockchain)
- **WORM storage:** Write-Once-Read-Many (Amazon S3 Object Lock, Azure Immutable Blob)

**Compliance queries:**
- SOC2: "Show all approvals for destructive operations in Q3 2024" → SQL query on audit store
- GDPR: "Show all approvals involving user X's data" → query by user_id
- HIPAA: "Show all approvals for PHI access" → query by resource_type=PHI

**Chain of custody:**
- ہر custody transfer (e.g., escalation) record ہو
- "Primary approver → Secondary approver at 2024-01-15 14:30 UTC, reason: timeout"

---

**سوال 17: Approval Delegation**

**Step-by-step delegation:**

1. **Delegation setup:**
   - Approver A delegation request: "Delegate to B from Jan 20 to Jan 27"
   - System validates: B exists، B has required permissions، B consents
   - Delegation record created with: delegator, delegate, start, end, scope

2. **Scope specification:**
   - Full delegation: B can approve/deny everything A could
   - Scoped delegation: B can only approve operations in "Department X" or "Tool Y"
   - Limit: B cannot re-delegate (no chain longer than 1)

3. **Active delegation:**
   - Approval requests during delegation period → routed to B
   - A's notifications paused
   - Audit log records both: "approved by B (delegated from A)"

4. **Revocation:**
   - A can revoke delegation anytime
   - Emergency revocation: immediate propagation
   - If B has pending approvals → re-routed to A

5. **Audit:**
   - Delegation creation, modification, revocation تمام logged
   - Every delegated approval marked as such in audit trail

**Edge cases:**
- B also goes on leave → fallback to escalation chain
- B's permissions change mid-delegation → re-validate, potentially revoke
- Delegation overlaps (A delegates to both B and C) → first delegation wins

---

**سوال 18: Emergency Break-Glass**

**Break-glass protocol:**

1. **Trigger:**
   - Production outage detected
   - Normal approval chain > 30 min response time
   - Operator initiates break-glass: "Emergency access to [resource] for [purpose]"

2. **Restrictions:**
   - **Scope:** Only the specific resource + operation requested
   - **Duration:** Max 2 hours, auto-revokes
   - **Single-use:** One operation, then expired
   - **Not for routine:** Rate limited (max 3 break-glass per week per person)

3. **Activation:**
   - Require 2-person rule: requester + secondary confirmer
   - OR: automated trigger based on incident severity (SEV1 → auto break-glass)

4. **Post-review:**
   - Within 24h: mandatory review by security team
   - Review: Was break-glass justified? Was scope appropriate? Any anomalies?
   - If unjustified → flag for security investigation

5. **Abuse prevention:**
   - Rate limiting: max 3/week
   - Pattern detection: if same person breaks glass repeatedly → investigation
   - Auto-alert: security team notified on every break-glass activation
   - Audit: every break-glass fully logged

---

**سوال 19: Approval Request Batching**

**Batch approval design:**

1. **Batch creation:**
   - Agent 50 files create کر رہا ہے → Gateway detects batch pattern (same operation, different resources)
   - Auto-group into single approval request: "Create 50 files in /reports/ (total: 2.5GB)"

2. **Summary presentation:**
   - Approver sees: operation type, count, total size, file list (collapsible), risk score
   - Sample preview: first 3 files shown in detail
   - "Select all" or "individual select" for partial approval

3. **Partial approval:**
   - Approver can approve 40, reject 10 (e.g., 10 files have wrong naming)
   - Rejected files: agent notified, can fix and re-request
   - Approved files: agent proceeds with those only

4. **Failure handling:**
   - If 5 of 40 approved files fail to create → retry those 5 (within approval scope)
   - If >50% fail → abort batch, notify approver

5. **Audit:**
   - Single approval record covers all 50 files
   - Individual file creation results logged separately
   - "Batch approval #123: 50 files, 40 approved, 10 rejected, 38 created successfully, 2 failed"

---

**سوال 20: Approval Decision Prediction**

**Predictive approval system:**

1. **Model training:**
   - Historical data: approval requests + decisions + context + approver
   - Features: operation type, resource type, risk score, approver history, time of day, agent, user
   - Model: gradient boosted trees or neural net
   - Output: probability of approval (0-1)

2. **Prediction confidence:**
   - P(approve) > 0.95 → auto-approve with post-hoc audit (high confidence)
   - P(approve) 0.7-0.95 → request approval (but pre-fill "likely approved" for approver)
   - P(approve) < 0.7 → request approval normally

3. **False positive rollback:**
   - If auto-approved مگر approver later disagrees → operation may have already executed
   - Mitigation: only auto-approve for **reversible** operations
   - For irreversible: even if P>0.95, still request human approval

4. **Model drift:**
   - Monthly retraining
   - Track prediction accuracy over time
   - If accuracy drops >5% → trigger retraining + investigation

**Reasoning:** Predictive approval approval fatigue کم کرتا ہے مگر wrong predictions سنگین ہو سکتی ہیں۔ اس لیے صرف reversible operations کے لیے، high confidence threshold، اور human-in-the-loop for irreversible۔

---

### Budget Management (سوال 21–30)

---

**سوال 21: Multi-Dimensional Budget Model**

**Dimensions:**
| Dimension | Unit | Rationale |
|---|---|---|
| Monetary | USD | Hard cost ceiling |
| Tokens | Count | LLM usage control |
| API calls | Count | Rate protection |
| Execution time | Seconds | Compute resource |
| Storage | GB | Data accumulation |
| Egress | GB | Network cost |

**Quota allocation:**
- ہر dimension کا soft limit (warning at 80%) اور hard limit (block at 100%)
- Soft limit → alert + throttle (reduce rate)
- Hard limit → block all new requests

**Conversion:**
- Monetary dimension دیگر تمام dimensions کا aggregate ہے (tokens → cost, API calls → cost, etc.)
- اگر token budget exhausted ہو مگر monetary میں room ہے → tokens خریدے جا سکتے ہیں (with alert)

---

**سوال 22: Budget Enforcement at Tool Level**

**Order: Budget check BEFORE policy check? یا بعد؟**

**Recommended order:**
1. Authentication (fast)
2. **Budget check** (fast — counter lookup)
3. Policy check (slower — attribute evaluation)
4. Approval check (slowest — human in loop)

**Reasoning:** اگر budget exhausted ہے تو policy evaluation waste ہے۔ Budget check pehle کریں۔

**Cost estimation:**
- Pre-execution estimate: `estimated_cost = historical_avg_cost(tool, operation_type, resource_size)`
- If estimate > remaining budget → deny before execution
- Post-execution actual: `actual_cost = measured_usage × unit_price`
- Reconciliation: `overage = actual - estimate` → if overage > 20%, flag for model recalibration

**Estimate error handling:**
- Conservative estimation: overestimate by 20% (better to deny than to overspend)
- If actual < estimate → credit back the difference
- If actual > estimate → charge the overage, flag the tool for recalibration

**Budget reservation:**
- Pre-execution: reserve `estimated_cost × 1.2` (20% buffer)
- During execution: actual consumed from reservation
- Post-execution: release unused reservation
- If reservation fails (insufficient budget) → deny

---

**سوال 23: Budget Hierarchy**

**Allocation tree:**
```
Platform (total budget)
  └─ Tenant-A (allocated: 50% of platform)
       └─ Dept-Engineering (allocated: 60% of tenant)
            └─ Project-Alpha (allocated: 40% of dept)
                 └─ User-X (allocated: 30% of project)
                      └─ Agent-1 (allocated: 100% of user allocation)
```

**Borrowing:**
- If Project-Alpha exhausts its budget → can request from Dept-Engineering's unallocated pool
- Borrowing requires: request → dept admin approval → temporary allocation
- Auto-repay: when project's regular budget resets, borrowed amount deducted first

**Reconciliation:**
- Monthly: actual usage vs allocated
- Overages: flag + charge to parent level
- Underages: carry forward (configurable, max 1 month)

---

**سوال 24: Rate Limiting Integration**

**Strategy:**

1. **Rate limiting:** Short-term burst control (per-second/minute)
   - Token bucket per tenant
   - Prevents sudden spikes from crashing downstream

2. **Budget:** Long-term consumption control (daily/monthly)
   - Total spend ceiling

3. **Integration:**
   - Rate limit checked first (fast, in-memory)
   - Budget checked second (slightly slower, may need DB lookup)
   - Both must pass for request to proceed

4. **Distributed rate limiting:**
   - Redis-based sliding window counter
   - All Gateway instances share rate limit state
   - Consistency: eventual (within ~100ms)

5. **Token bucket with budget dimensions:**
   - Bucket refill rate = configured rate limit
   - Bucket capacity = burst limit
   - Budget dimension: each token consumed = 1 API call + X tokens + Y cost
   - When budget exhausted → bucket stops refilling (even if rate limit allows)

---

**سوال 25: Budget Alerting**

**Thresholds:**
- 50% → INFO alert (awareness)
- 80% → WARNING alert (prepare)
- 95% → CRITICAL alert (action needed)
- 100% → EMERGENCY alert (exhausted)

**Alert fatigue prevention:**
- Throttle: max 1 alert per threshold per day per project
- Aggregation: batch alerts (e.g., "5 projects at 80%")
- Smart routing: alerts go to project owner, not everyone
- Auto-resolution: if usage drops below threshold, send resolution alert

**Predictive alerting:**
- Linear extrapolation: at current rate, budget will exhaust in X days
- Alert: "At current burn rate, budget will exhaust in 3 days"
- ML-based: seasonal patterns (e.g., end-of-month spikes)

**Channels:**
- Email (default)
- Slack/Teams integration
- Webhook (custom)
- Dashboard (always visible)

---

**سوال 26: Budget Rollover and Reset**

**Monthly reset:**
- 1st of month: budget counter reset to allocated amount
- Unused budget from previous month → configurable rollover (default: 0%, max 20%)

**Mid-month onboarding:**
- Tenant joins on 15th → prorated budget (50% of monthly allocation)
- Next month: full allocation

**Billing changes:**
- If allocation increased mid-month → new amount from effective date
- If allocation decreased → check if current usage > new allocation → if yes, overage flag

**Billing cycles:**
- Configurable: monthly (default), quarterly, annual
- Reset date: configurable (e.g., 1st of month, or anniversary date)

---

**سوال 27: Budget Anomaly Detection**

**Algorithm:**
1. **Baseline:** Rolling 7-day average usage per agent/tenant
2. **Anomaly score:** Current hour usage / baseline
3. **Threshold:** >3x baseline = anomaly
4. **ML enhancement:** Isolation Forest or statistical process control (control charts)

**Response actions:**
- Score 3-5x: Alert + throttle (reduce rate by 50%)
- Score 5-10x: Alert + suspend agent (require re-activation)
- Score >10x: Alert + kill switch candidate (possible compromised agent)

**False positive handling:**
- Known patterns (e.g., monthly batch job) → whitelist
- First-time anomaly → alert only (no action), if repeats → action
- User can acknowledge anomaly (feedback loop for ML)

**Investigation:**
- Agent's recent task history
- Which tools consumed most
- Was there a code change (new tool call pattern)?

---

**سوال 28: Cost Attribution and Showback**

**Cost attribution:**
- Per tool call: `agent_id → tool_call_id → cost_breakdown`
- Cost breakdown: tokens, API cost, compute time, storage, network
- Shared resources: prorate by usage (e.g., shared model instance → cost per request × instance cost / total requests)

**Showback report:**
```
Agent: report-generator-1
Task: "Generate Q3 Sales Report"
  - LLM tokens: 45,000 tokens ($0.45)
  - Browser calls: 12 ($0.12)
  - File storage: 500MB ($0.01)
  - Execution time: 180s ($0.03)
  - Total: $0.61
```

**Showback vs chargeback:**
- Showback: show cost to team, no billing (awareness)
- Chargeback: actually bill the team's budget (accountability)
- Recommendation: Showback first (month 1-3), then chargeback (month 4+)

---

**سوال 29: Budget Negotiation**

**Negotiation protocol:**
1. Agent requests additional budget: "Need $50 more for task X (reason: larger-than-expected dataset)"
2. Gateway evaluates: is request reasonable? Compare to historical similar tasks
3. Gateway counter-offer: "Can allocate $30 (based on median cost for similar tasks)"
4. Agent accepts/rejects/counter-negotiates
5. Max 3 rounds, then final decision

**Audit:**
- Every negotiation round logged
- Final agreed amount vs requested amount
- Who approved the additional budget
- Was the additional budget justified (post-task analysis)

---

**سوال 30: Budget-Aware Task Planning**

**Pre-task planning:**
1. Agent decomposes task into steps
2. Each step's cost estimated:
   - Step 1: Web search → ~$0.05
   - Step 2: Data processing (code execution) → ~$0.02
   - Step 3: LLM analysis (10K tokens) → ~$0.10
   - Step 4: Report generation → ~$0.05
   - Total estimate: ~$0.22
3. Compare to remaining budget
4. If insufficient → present alternatives to user:
   - Plan A (full): $0.22, high quality
   - Plan B (reduced): $0.10, lower quality (fewer sources, less analysis)
   - Plan C (minimal): $0.05, basic summary only

**Runtime re-planning:**
- If step 2 costs $0.15 instead of $0.02 (unexpected):
  - Re-evaluate remaining plan
  - If total will exceed budget → truncate or simplify remaining steps
  - Notify user: "Step 2 was more expensive, reducing step 3 scope"

---

### Capability Lease (سوال 31–40)

---

**سوال 31: Capability Lease Model**

**Concept:**
- **Capability:** A permission to use a specific tool with specific constraints (e.g., "browser access to *.example.com for 1 hour")
- **Lease:** Time-bound grant of that capability to an agent
- **One-time check:** Stateless permission check per request (no persistence)

**Lease vs one-time check:**
| Aspect | Lease | One-time check |
|---|---|---|
| State | Stateful (track active leases) | Stateless |
| Revocation | Immediate (revoke lease) | Not possible (next request only) |
| Overhead | Medium (lease store) | Low (per-request eval) |
| Use case | Long-running ops, continuous auth | Simple, one-shot operations |

**Acquisition flow:**
1. Agent requests capability: "I need browser access"
2. Gateway evaluates: policy + budget + risk
3. If approved → lease created with: `lease_id`, `capability`, `agent_id`, `expiry`, `constraints`
4. Agent uses lease for all subsequent tool calls (presents lease_id)
5. Gateway validates lease per call: is it valid? not revoked? not expired?

---

**سوال 32: Lease Revocation**

**Revocation propagation:**
1. Security team issues global revoke: "Revoke all browser leases for Tenant-A"
2. Revocation record written to lease store (consistent, fast)
3. Active browser operations:
   - Gateway checks lease on every tool call
   - Next tool call → lease revoked → operation denied
   - **In-flight HTTP request:** Cannot interrupt mid-request, but block all subsequent requests
   - **Long-running browser session:** Send abort signal, close session
4. Agent acknowledgment:
   - Agent receives revocation notification
   - Agent must acknowledge before requesting new capabilities
5. Partial revocation:
   - Revoke specific domain access but keep other domains
   - Lease updated with narrower scope

**Timing:**
- Propagation latency: <1 second (synchronous lease check per call)
- Active in-flight operations: complete or abort (configurable)

---

**سوال 33: Lease Negotiation**

**Protocol:**
1. Agent: "Requesting browser lease, scope: all domains, duration: 2 hours"
2. Gateway evaluates policy → partial allow: "Browser OK, but scope: *.trusted.com only, duration: 30 min"
3. Agent: "Can I get 1 hour? Need to access 3 different sites"
4. Gateway: "1 hour OK, but scope: 3 specific URLs, not wildcard"
5. Agent accepts or rejects

**Progressive lease:**
- Start with minimal scope (30 min, 1 URL)
- As agent demonstrates safe behavior → expand (more URLs, longer duration)
- "Trust building" — similar to progressive access control

**Failure:**
- If negotiation fails → agent operates without capability (degraded mode) or aborts task

---

**سوال 34: Lease Dependencies**

**Dependency graph:**
```
Email capability
  └─ depends on → Network access capability
  └─ depends on → Address book access capability

File write capability
  └─ depends on → Directory access capability
```

**Transitive revocation:**
- If "Network access" revoked → "Email" lease automatically revoked (dependency broken)
- Revocation propagates through dependency graph

**Acquisition order:**
- Acquire dependencies first: Network → Address book → Email
- If any dependency fails → don't acquire dependent lease

**Orphaned leases:**
- If parent lease expires but child still active → child auto-revoked
- Detection: periodic sweep for orphaned leases (every 60s)

---

**سوال 35: Lease Renewal**

**Renewal flow:**
1. Lease approaching expiry (T-5 min): Gateway sends renewal notification to agent
2. Agent sends renewal request
3. Gateway re-evaluates: policy still allows? budget available? risk unchanged?
4. If approved → extend lease (new expiry)
5. If denied → lease expires on schedule, agent must release resources

**Continuous renewal prevention:**
- Max lease duration: 24 hours (hard cap)
- Max renewals: 5 per lease (then must re-acquire from scratch)
- If agent continuously renews same lease >5 times → flag for investigation (possible infinite loop)

---

**سوال 36: Lease Scope and Granularity**

**Fine-grained:**
- "Browser access to https://specific-site.com/api/v1/data, GET only, 30 min"
- Pros: Minimal blast radius, precise audit
- Cons: Many lease requests, overhead

**Coarse-grained:**
- "Browser access, any URL, 2 hours"
- Pros: Fewer requests, less overhead
- Cons: Larger blast radius if compromised

**Recommendation:** Start coarse, narrow if risk detected:
- Initial: coarse (reduce friction)
- After anomaly: narrow to fine-grained
- Risk-based: high-risk tools → fine, low-risk → coarse

**Scope specification:**
- Use structured format: `{tool: "browser", actions: ["GET"], resources: ["https://*.example.com/*"], duration: "30m"}`

---

**سوال 37: Lease Transfer**

**Constraints:**
1. Same tenant only (no cross-tenant transfer)
2. Recipient must have underlying permission (policy must allow recipient to have this capability)
3. Transfer record: who, to whom, when, why, lease details
4. Original lease invalidated after transfer (no duplication)

**Audit:**
- Transfer logged: `from_agent`, `to_agent`, `lease_id`, `timestamp`, `reason`
- Recipient's usage of transferred lease attributed to original agent for cost

**Revocation:**
- If original agent's permissions revoked → transferred lease also revoked (can't bypass revocation via transfer)
- If recipient's permissions revoked → transferred lease revoked

---

**سوال 38: Lease Quotas**

**Enforcement:**
- Per tenant: max 100 concurrent active leases
- When limit reached: new lease requests denied with "quota exceeded"
- Error includes: current count, limit, suggestion to release unused leases

**Prioritization:**
- High-priority agents (e.g., production-critical) can preempt low-priority leases
- Priority levels: critical > high > normal > low

**Borrowing:**
- Tenants can request additional quota from platform pool
- Borrowed quota returned at end of billing cycle

**Scaling:**
- Auto-scaling: if tenant consistently uses >80% of quota → suggest quota increase
- Hard cap: platform-level max (e.g., 1000 per tenant) to prevent resource exhaustion

---

**سوال 39: Lease Encryption**

**Token format:**
```
lease_token = base64(header).base64(payload).base64(signature)
header = {"alg": "ES256", "typ": "LEASE"}
payload = {"lease_id", "agent_id", "tenant_id", "capability", "expiry", "constraints", "fencing_token"}
signature = ECDSA(private_key, header + payload)
```

**Signing:**
- Asymmetric signing (ECDSA P-256)
- Private key: Gateway only (signs)
- Public key: all components (verify)
- Key rotation: every 90 days, old tokens valid until expiry

**Replay protection:**
- `fencing_token`: monotonically increasing number per lease
- Each tool call must include fencing_token
- Gateway tracks highest fencing_token seen — reject if lower
- Prevents replay of old (pre-revocation) tokens

---

**سوال 40: Lease Observability**

**Metrics:**
| Metric | Type |
|---|---|
| `active_leases` | Gauge (per tenant, per capability) |
| `lease_acquisitions` | Counter |
| `lease_renewals` | Counter |
| `lease_revocations` | Counter |
| `lease_expiry_total` | Counter |
| `lease_duration` | Histogram |
| `lease_quota_utilization` | Gauge (%) |

**Lifecycle events:**
- Create, renew, revoke, expire, transfer — all logged with context

**Anomaly detection:**
- Unusual acquisition pattern (sudden spike in lease requests)
- Long-lived leases (> expected duration)
- Lease transfers (should be rare — flag if frequent)

**Forensic analysis:**
- Timeline reconstruction: "Agent X acquired browser lease at T1, accessed URLs at T2-T5, lease revoked at T6"
- Cross-reference with audit logs for complete picture

---

### Audit System (سوال 41–50)

---

**سوال 41: Comprehensive Audit Trail**

**Events to capture:**
- Tool calls (request, response, duration, result)
- Policy decisions (evaluated, allowed/denied, rules matched)
- Approval events (requested, approved, rejected, expired)
- Budget events (allocated, consumed, exhausted)
- Lease events (acquired, renewed, revoked)
- Kill switch events (activated, deactivated)
- Authentication events (login, token issued, revoked)
- Configuration changes (policy updates, threshold changes)

**Mandatory fields:**
```
timestamp, event_type, actor_id, tenant_id, agent_id,
tool_name, operation, resource, result, risk_score,
policy_version, request_id, trace_id, ip_address,
session_id, correlation_id
```

**Immutability guarantee:**
- Append-only storage (no UPDATE/DELETE)
- Cryptographic chaining (each record's hash includes previous record's hash)
- WORM storage backend (S3 Object Lock, Azure Immutable Blob)
- Hash chain root published externally (for tamper detection)

**Retention policy:**
- Hot storage (queryable): 90 days
- Cold storage (compressed): 7 years (compliance requirement)
- After 7 years: secure deletion with deletion certificate

---

**سوال 42: Audit Data Volume Management (43 TB/day)**

**Data pipeline:**
1. **Ingestion:** Kafka (partitioned by tenant_id for parallelism)
2. **Stream processing:** Flink/Spark Streaming for real-time processing
3. **Hot storage:** Elasticsearch (90 days, full-text search)
4. **Cold storage:** S3/GCS with Parquet format (compressed, 7 years)

**Sampling:**
- **Full capture:** All policy decisions, approvals, kill switch events, denials, errors
- **Sampled (10%):** Routine allowed tool calls (if volume too high)
- **Aggregated:** Per-minute summaries for metrics (count, avg latency, etc.)

**Indexing:**
- Hot: index on (tenant_id, timestamp, event_type)
- Cold: partition by date, columnar format for efficient queries

**Cost optimization:**
- Compression: Parquet (10:1 ratio for JSON audit data)
- Tiered storage: hot (SSD, 90d) → warm (HDD, 1yr) → cold (S3, 7yr)
- Auto-archival: data older than 90 days → move to cold automatically

---

**سوال 43: Real-time Audit Monitoring**

**Streaming architecture:**
1. Audit events → Kafka topic
2. Flink streaming job processes events in real-time
3. Complex Event Processing (CEP) for pattern detection

**CEP patterns:**
- **Sudden denial spike:** >50 denials in 1 minute from same agent → alert
- **Scanning pattern:** Agent accessing sequential resources (possible enumeration) → alert
- **After-hours activity:** Tool calls from agent at 3 AM → alert
- **Privilege escalation chain:** Multiple approval requests escalating → alert
- **Data exfiltration pattern:** Large file reads followed by external sends → CRITICAL alert

**Alert correlation:**
- Group related alerts (same agent, same timeframe) into incidents
- Deduplicate similar alerts
- Severity scoring: low + low + low = medium incident

**False positive reduction:**
- Whitelist known patterns (batch jobs, scheduled tasks)
- ML-based: learn normal behavior, only alert on deviations
- Feedback loop: analysts mark FPs, system learns

---

**سوال 44: Audit for Compliance**

**Compliance views:**
- **SOC2:** Access controls, change management, security monitoring
- **GDPR:** PII access, data subject rights, breach notification
- **HIPAA:** PHI access, minimum necessary, audit controls

**Automated checks:**
- Daily: "Were there any policy bypasses?" → query audit log for denied+executed
- Weekly: "Were all approvals properly logged?" → verify approval records complete
- Monthly: "Were there any unauthorized access attempts?" → query denials

**Evidence collection:**
- Automated report generation: PDF with queries + results + charts
- Evidence package: audit log excerpts + policy versions + approval records
- Hash chain verification: prove audit log not tampered with

**Auditor access:**
- Read-only access to audit data
- Pre-defined query templates (auditors don't write SQL)
- Access logged (meta-audit: auditing the auditors)

---

**سوال 45: Audit Data Privacy**

**Data classification:**
- Level 1 (Public): Tool names, operation types, timestamps
- Level 2 (Internal): User IDs, resource names, agent IDs
- Level 3 (Confidential): File paths, query parameters, email recipients
- Level 4 (PII/Sensitive): Email content, file content, personal data

**Masking:**
- Level 3: Partial mask (e.g., `/home/user/***`)
- Level 4: Full mask + hash reference (e.g., `PII_DATA_HASH:a1b2c3`)
- Configurable per tenant's privacy requirements

**Encryption:**
- At rest: AES-256
- In transit: TLS 1.3
- Field-level: PII fields encrypted separately with tenant-specific key

**Access control:**
- Audit data access = least privilege
- Level 1-2: ops team, security team
- Level 3: security team + compliance team
- Level 4: compliance team only, with justification log

---

**سوال 46: Audit Chain of Custody**

**Timeline reconstruction:**
1. Incident detected at T0
2. Query audit log: all events for involved agents/users from T0-24h to T0
3. Timeline: chronological list of all actions
4. Correlation: link events by trace_id, request_id, session_id

**Evidence integrity:**
- Hash chain: verify chain from incident event back to genesis
- Any broken chain = tampering detected
- Export evidence: signed bundle (events + hash chain + verification proof)

**Custody transfer:**
- When evidence handed to legal team: custody transfer logged
- "Evidence bundle #123 transferred from Security Team to Legal Team at [timestamp], signed by [person]"

**Court-admissible:**
- Chain of custody documentation
- Hash verification certificates
- Timestamp authority (RFC 3161 timestamps)
- Expert witness testimony preparation (system design documentation)

---

**سوال 47: Audit Performance Impact**

**Synchronous vs asynchronous:**
- **Policy decisions:** Synchronous audit (must log before responding — compliance)
- **Tool call results:** Asynchronous (buffer + batch write — performance)
- **Approval events:** Synchronous (compliance critical)

**Buffering:**
- In-memory ring buffer (lock-free, ~1ms overhead)
- Batch flush every 100ms or 1000 events (whichever first)
- If buffer full → drop oldest (with counter) — prefer availability over completeness for non-critical events

**Degradation:**
- If audit system overloaded → degrade gracefully:
  1. Sample non-critical events (every 10th)
  2. Drop debug-level events
  3. Reduce fields per event
  4. Last resort: queue locally, replay when audit system recovers

**Performance target:**
- Audit overhead: <1% of request latency
- Audit write: <5ms (batched)
- Audit system failure: does NOT block main execution (except for compliance-critical events)

---

**سوال 48: Audit Across Distributed Components**

**Distributed tracing:**
- OpenTelemetry trace context propagated across all components
- Each component adds spans to the trace
- Single trace_id links all audit events from one logical operation

**Clock synchronization:**
- NTP (precision: ~10ms) — acceptable for most audit purposes
- For higher precision: hybrid logical clocks (HLC) — combine physical time with logical counter
- Events ordered by: (1) trace_id, (2) span parent-child, (3) timestamp

**Causal ordering:**
- If event A causes event B → A must appear before B in audit log
- Enforced by: parent_span_id → child_span_id ordering
- Clock skew handled by: if A.parent == B → A before B regardless of timestamp

**Partial failure:**
- If one component's audit system fails → events buffered locally
- On recovery → replay buffered events (with original timestamps)
- Gap in audit log → flagged as "audit gap" for investigation

---

**سوال 49: Audit Data Query and Analysis**

**Query language:**
- SQL-like query interface (for analysts)
- Lucene/full-text (for security team, keyword search)
- Time-series (for trend analysis)

**Example queries:**
```sql
-- All denials for Tenant-A in last 24h
SELECT * FROM audit_events 
WHERE tenant_id='A' AND result='DENIED' AND timestamp > NOW() - 24h
ORDER BY timestamp DESC;

-- Top 10 agents by tool call volume
SELECT agent_id, COUNT(*) as calls 
FROM audit_events 
WHERE event_type='TOOL_CALL' 
GROUP BY agent_id ORDER BY calls DESC LIMIT 10;
```

**Performance:**
- Hot queries: pre-aggregated (per-minute, per-hour rollups)
- Cold queries: columnar scan with predicate pushdown (Parquet + S3 Select)
- Query timeout: 30s (prevent runaway queries)

**Visualization:**
- Dashboards: Grafana/Kibana
- Timeline view: for forensic analysis
- Heatmaps: activity patterns by time/agent
- Graph view: agent-tool-resource relationships

---

**سوال 50: Audit-Based Anomaly Detection**

**Feature extraction:**
- Per agent: call frequency, tool diversity, resource access patterns, time-of-day distribution
- Per tenant: total volume, tool distribution, anomaly rate
- Temporal: hourly/daily/weekly patterns

**Behavioral baselining:**
- Rolling 30-day baseline per agent
- Baseline includes: avg calls/hour, tool distribution, resource types accessed, error rate

**Anomaly scoring:**
- Z-score per feature (how many std dev from baseline)
- Composite score: weighted sum of z-scores
- Isolation Forest for multivariate anomaly detection

**Investigation pipeline:**
1. Anomaly detected (score > threshold)
2. Auto-collect context: agent's recent activity, policy decisions, audit trail
3. Create investigation ticket
4. Alert security analyst with full context
5. Analyst reviews → confirms/dismisses
6. Feedback: confirmed anomaly → retrain model; dismissed → adjust threshold

---

### Kill Switch (سوال 51–55)

---

**سوال 51: Kill Switch Activation**

**Activation mechanism:**
1. **Manual:** Admin clicks "Kill All Agents" button in dashboard
   - Requires 2-person confirmation (prevent accidental activation)
2. **Automated:** Triggered by anomaly detection (see Q54)
3. **Scoped:** "Kill all agents for Tenant-A" or "Kill all agents using tool X"

**Propagation:**
- Kill switch activation → broadcast message to all Gateway instances via Redis pub/sub
- Gateway instances propagate to all connected agents via WebSocket/SSE
- Agents receive kill signal → immediate graceful shutdown (save state, release resources)

**Latency:**
- Target: <5 seconds from activation to all agents stopped
- Breakdown: 1s broadcast + 2s agent acknowledgment + 2s graceful shutdown

**Scoped activation:**
- Per tenant: stop only Tenant-A's agents
- Per tool: stop all agents currently using browser tool
- Per agent: stop specific agent
- Per region: stop agents in specific region (datacenter issue)

---

**سوال 52: Kill Switch Recovery**

**Recovery procedure:**
1. **Investigate root cause:** Why was kill switch activated?
2. **Fix root cause:** Deploy fix, verify
3. **Gradual recovery:**
   - Phase 1: 10% of agents resume (canary)
   - Phase 2: 50% resume (if Phase 1 stable for 15 min)
   - Phase 3: 100% resume (if Phase 2 stable for 30 min)
4. **Monitor closely:** Elevated monitoring for 2 hours post-recovery

**Agent state:**
- Agents that saved state (checkpoints) → resume from checkpoint
- Agents that didn't save → restart from beginning
- In-flight operations: may need re-execution (check idempotency keys)

**Post-mortem:**
- Within 48h: written post-mortem document
- Timeline, root cause, impact, actions taken, lessons learned
- Action items tracked to completion

---

**سوال 53: Kill Switch Testing**

**Testing strategy:**
1. **Dry-run mode:** Activate kill switch in "simulation" mode
   - Agents receive signal but don't actually stop
   - System logs what would have happened
   - Verify: all agents received signal? Latency? Any gaps?

2. **Staging environment:** Full kill switch test in staging
   - Real agent shutdown but no production impact
   - Measure: propagation time, agent acknowledgment rate, recovery time

3. **Automated testing:**
   - Daily: dry-run kill switch test (verify signal propagation)
   - Weekly: staging environment full test
   - Quarterly: production canary test (kill 1% of agents in production)

4. **Metrics:**
   - Propagation latency: <5s target
   - Acknowledgment rate: >99% of agents
   - Recovery time: <5 min for canary phase

---

**سوال 54: Kill Switch Decision Logic**

**Automated triggers:**
1. **Budget anomaly:** Agent consuming >10x baseline budget → kill candidate
2. **Security incident:** Data exfiltration pattern detected → immediate kill
3. **Error cascade:** >50% of agent tool calls failing in 5 min → kill (preventive)
4. **Policy violation rate:** >20% of requests being denied → kill (agent misbehaving)
5. **External signal:** Security team's SIEM integration triggers kill

**Confidence threshold:**
- Single signal: confidence = 0.5 → alert only
- Two corroborating signals: confidence = 0.8 → scoped kill (agent level)
- Three+ signals: confidence = 0.95 → tenant-level kill
- Manual override always available

**False positive mitigation:**
- Grace period: 30s between detection and kill (allows agent to self-correct)
- Whitelist: known batch jobs exempted from kill triggers
- Reversibility: if FP detected → immediate recovery

**Escalation ladder:**
1. Throttle agent (reduce rate by 80%)
2. Pause agent (stop new tasks, let in-flight complete)
3. Kill agent (stop everything immediately)
4. Kill tenant agents (scope escalation)
5. Kill all agents (global)

---

**سوال 55: Kill Switch Audit**

**Event capture:**
```
{
  "event_type": "KILL_SWITCH",
  "activation_id", "timestamp", "activated_by" (user/system),
  "scope" (global/tenant/agent), "trigger_reason",
  "agents_affected_count", "propagation_latency_ms",
  "acknowledgment_rate", "recovery_timestamp",
  "post_mortem_id"
}
```

**Pre-activation snapshot:**
- System state at activation: agent count, active tasks, budget usage, error rates
- This snapshot helps understand "what was happening when we pulled the plug"

**Post-activation timeline:**
- Every recovery phase logged with timestamp
- Every agent's acknowledgment logged
- Any agents that didn't respond → investigated

**Compliance reporting:**
- Kill switch activation = major incident
- Report to: security team, compliance team, management
- Required fields: who, what, when, why, impact, resolution
- Retention: 7 years (same as audit trail)

---

### Tenant Isolation (سوال 56–60)

---

**سوال 56: Tenant Isolation Architecture**

**Isolation levels (from shared to dedicated):**

| Level | Model | Isolation | Cost |
|---|---|---|---|
| 1 | Shared DB, shared schema | Logical (tenant_id) | Lowest |
| 2 | Shared DB, separate schema | Schema-level | Low |
| 3 | Separate DB per tenant | DB-level | High |
| 4 | Separate infrastructure | Physical | Highest |

**Recommended for GNW:** Level 2 (shared DB, separate schema) for most tenants, Level 3 for enterprise/regulatory tenants.

**Tenant boundary enforcement:**
1. Every query includes `WHERE tenant_id = ?`
2. ORM-level tenant filter (automatic injection)
3. Application-level: tenant context in every request (JWT claim)
4. Network-level: tenant-specific network policies (if Level 3+)

**Cross-tenant communication:**
- **Default:** No cross-tenant communication (hard boundary)
- **Platform-level:** Platform admin can access all tenants (audited)
- **Federated:** If tenants opt-in, specific cross-tenant features (e.g., shared model instance)

**Onboarding:**
1. Create tenant record
2. Allocate budget quota
3. Create schema/DB
4. Deploy default policies
5. Create admin user
6. Verify isolation (automated test: try to access another tenant → must fail)

---

**سوال 57: Tenant Isolation Verification**

**Test cases:**
1. **Data access:** Tenant-A user queries Tenant-B data → must return 0 rows
2. **Policy leak:** Tenant-A's policy rules don't affect Tenant-B's decisions
3. **Cache leak:** Tenant-A's cached results not served to Tenant-B
4. **Audit access:** Tenant-A cannot query Tenant-B's audit logs
5. **Budget leak:** Tenant-A's budget not counted against Tenant-B

**Automated testing:**
- CI/CD pipeline: every deploy runs tenant isolation test suite
- Daily: automated cross-tenant access attempts (penetration test)
- Test framework: create two test tenants, attempt cross-access, verify denial

**Penetration testing:**
- Quarterly: external security firm tests isolation
- Test methods: SQL injection, API manipulation, JWT tampering, cache poisoning
- Report: isolation vulnerabilities → immediate fix required

**Metrics:**
- Isolation test pass rate: 100% (anything less = critical bug)
- Cross-tenant access attempts: tracked (denied attempts = healthy)
- Time to detect isolation breach: <1 min (automated monitoring)

---

**سوال 58: Tenant Identity Federation**

**Federation protocols:**
- **SAML 2.0:** Enterprise standard (Azure AD, Okta)
- **OIDC (OpenID Connect):** Modern, JSON-based (Google Workspace)
- **SCIM:** For user provisioning/deprovisioning

**Identity mapping:**
- External IdP user → GNW internal user
- Mapping table: `external_idp_id` ↔ `gnw_user_id`
- Attributes synced: email, name, department, role

**JIT (Just-In-Time) provisioning:**
- User logs in via SSO → if GNW user doesn't exist → auto-create
- Default role: "member" (least privilege)
- Admin must elevate to higher role

**Identity sync:**
- Scheduled sync (daily): full directory sync from IdP
- Real-time sync (SCIM): user creation/deletion in IdP → immediate GNW update
- Conflict resolution: IdP is source of truth → GNW overwrites local

---

**سوال 59: Tenant Resource Fairness**

**Fairness model:**
- **Equal share:** Each tenant gets 1/N of resources
- **Weighted:** Tenants with higher tier get more (Gold=3x, Silver=2x, Bronze=1x)
- **Guaranteed minimum:** Every tenant gets minimum X% regardless of others

**Resource isolation:**
- Compute: cgroups / Kubernetes resource quotas per tenant
- Network: bandwidth limits per tenant
- Storage: quota per tenant

**Noisy neighbor detection:**
- Monitor: per-tenant resource utilization vs allocation
- If Tenant-A consistently uses >80% of shared resources while others wait → noisy neighbor
- Response: throttle Tenant-A, alert admin

**Fairness metrics:**
- Resource allocation fairness (Jain's fairness index)
- Per-tenant latency comparison (should be similar)
- Per-tenant throughput vs allocation ratio

---

**سوال 60: Tenant Data Lifecycle**

**Offboarding steps:**
1. **Initiate:** Tenant admin requests offboarding (or platform admin for non-payment)
2. **Data export:** All tenant data exported (files, audit logs, memory, configs) in standard format
   - Export to: S3 bucket / Google Cloud Storage / Azure Blob
   - Format: JSON + files (human-readable where possible)
   - Timeframe: 30 days to complete
3. **Secure deletion:**
   - Database: DROP SCHEMA (Level 2) or DROP DATABASE (Level 3)
   - Files: secure delete (overwrite + delete)
   - Cache: invalidate all tenant cache entries
   - Backups: mark for deletion (next backup cycle)
   - Vector DB: delete all tenant embeddings
4. **Retention requirements:**
   - Audit logs: retained per compliance (7 years) but anonymized (tenant_id removed, data hashed)
   - Financial records: retained per tax law
5. **Offboarding audit:**
   - Deletion certificate: what was deleted, when, by whom
   - Verification: attempt to access tenant data → must return nothing
   - Retention: offboarding audit kept for 7 years

---

### Action Deduplication (سوال 61–65)

---

**سوال 61: Idempotency Architecture**

**Key generation:**
- Client (agent) generates idempotency key BEFORE making request
- Key format: `idem_{agent_id}_{task_id}_{step_hash}_{nonce}`
- Agent includes key in request header: `Idempotency-Key: idem_abc123...`

**Key storage:**
- Distributed store: Redis (for fast lookup) + PostgreSQL (for durability)
- Key lifecycle:
  - Created: when request received
  - In-progress: while processing
  - Completed: result stored alongside key
  - Expired: TTL 24 hours (configurable)

**Lifecycle:**
1. Request arrives with key → check if key exists in store
2. If not exists → create entry, process request, store result
3. If exists and in-progress → return "processing" status (don't duplicate)
4. If exists and completed → return cached result (don't re-execute)
5. After TTL → key expires, can be reused (acceptable risk after 24h)

---

**سوال 62: Duplicate Detection**

**Detection logic:**
1. Extract idempotency key from request
2. Query store: `SELECT * FROM idempotency WHERE key = ?`
3. If found:
   - Status = completed → return stored result (duplicate detected, legitimate retry)
   - Status = in-progress → return 202 "Processing" (concurrent duplicate)
   - Status = failed → allow re-execution (legitimate retry after failure)
4. If not found → new request, proceed normally

**Concurrent duplicates:**
- Two requests with same key arrive simultaneously → race condition
- Solution: distributed lock on key (Redis SETNX)
- First request acquires lock → processes
- Second request waits → gets cached result

**Partial completion:**
- If first request partially completed then crashed:
  - Idempotency entry = in-progress (never marked completed)
  - Next retry: detect in-progress with timeout → re-process
  - **Idempotent operation:** safe to re-execute (no side effects duplication)
  - **Non-idempotent operation:** need compensating transaction

**Collision:**
- Probability of UUID collision: ~1 in 2^122 (negligible)
- If agent generates key deterministically (hash of request) → collision possible if identical requests
- This is expected behavior (identical request = legitimate duplicate)

---

**سوال 63: Idempotency in Distributed Systems**

**Cross-instance sharing:**
- All Gateway instances share idempotency store (Redis cluster)
- Consistency model: strong consistency for key existence (Redis SETNX is atomic)
- Availability: if Redis unavailable → degrade to per-instance idempotency (weaker but functional)

**CAP trade-off:**
- **CP:** Consistency + Partition tolerance → if network partition, deny requests (can't verify idempotency)
- **AP:** Availability + Partition tolerance → allow requests, risk duplicates
- **Recommendation:** CP for destructive operations, AP for read-only

**Cross-region:**
- If multi-region deployment → idempotency store per region
- Cross-region requests: include region in key, check local store first, remote if needed
- Eventual consistency: <1s lag between regions (acceptable for most cases)

**Store failure:**
- If idempotency store fails:
  - Degrade to "no idempotency" mode (accept duplicates risk)
  - OR: fail-closed for destructive ops (deny until store recovers)
  - Configuration per tool type

---

**سوال 64: Idempotency Key Design**

**Parameters to include:**
- agent_id (who)
- tool_name (what tool)
- operation (what operation)
- primary parameters (resource ID, URL, file path)
- intent hash (hash of full request for integrity)

**Parameters to exclude:**
- timestamp (would make every request unique — defeats purpose)
- request_id (unique per request, not per operation)
- transient metadata (trace_id, session_id)

**Intent-based vs parameter-based:**
- **Parameter-based:** Key = hash(agent_id + tool + params) → same params = same key
  - Pro: deterministic, simple
  - Con: if params slightly different (e.g., different timestamp in data) → different key
- **Intent-based:** Key = hash(agent_id + tool + intent_description)
  - Pro: "send email to team about Q3 report" → same key even if content slightly different
  - Con: requires LLM to generate intent description (unreliable)

**Recommendation:** Parameter-based with normalized parameters (strip volatile fields like timestamps, request_ids).

**Collision probability:**
- SHA-256 hash: collision probability ~1 in 2^128 (negligible)
- If using shorter keys (64-bit): ~1 in 4 billion per billion keys — add salt if concerned

---

**سوال 65: Idempotency and Exactly-Once Semantics**

**Exactly-once vs at-least-once + idempotency:**

| Approach | Mechanism | Complexity | Performance |
|---|---|---|---|
| Exactly-once | Two-phase commit | Very high | Low (blocking) |
| At-least-once + idempotency | Retry + dedup | Medium | High |

**Recommendation:** **At-least-once + idempotency** for GNW.

**Reasoning:**
- Exactly-once requires distributed consensus (2PC) → high latency, complex failure handling
- At-least-once + idempotency achieves the same effect (operation executed once) with simpler design
- Idempotency at application level: if operation is safe to retry (no side effects on retry), then at-least-once delivery is fine

**Outbox pattern:**
1. Agent writes to local DB + outbox table in same transaction
2. Outbox processor reads + sends to Gateway
3. If send fails → retry (idempotency key prevents duplicate execution)
4. If Gateway processes → ack → mark outbox entry as processed
5. Guarantees: message sent at-least-once, executed exactly-once (idempotency)

**Real-world limitations:**
- 2PC: not supported by all systems (e.g., many NoSQL databases)
- Network partitions: exactly-once impossible during partition (must choose CP or AP)
- Performance: 2PC adds 3-5x latency
- Conclusion: at-least-once + idempotency is the pragmatic choice

---

### Tool Selection Rules (سوال 66–70)

---

**سوال 66: Tool Selection Decision Framework**

**Step-by-step decision:**

1. **Capability matching:**
   - Task requirement: "I need to search the web for current stock prices"
   - Tool capabilities: browser (web search), code executor (API calls), API connector (stock API)
   - Match: browser (general web search) OR stock API (specific, reliable)

2. **Selection criteria:**
   - **Accuracy:** Stock API > browser (structured data vs scraped)
   - **Speed:** Stock API (~100ms) > browser (~2s)
   - **Cost:** Stock API ($0.01) < browser ($0.05)
   - **Reliability:** Stock API (99.9% SLA) vs browser (may hit CAPTCHA)
   - **Freshness:** Stock API (real-time) vs browser (may be cached)

3. **Multi-tool workflows:**
   - Sometimes one tool isn't enough:
     - Step 1: Browser → find company's investor relations page
     - Step 2: Browser → extract financial data
     - Step 3: Code executor → calculate ratios
     - Step 4: File writer → save report

4. **Audit:**
   - Every tool selection decision logged: why this tool was chosen, what alternatives considered
   - Enables post-hoc analysis: "Why did agent choose browser over API?"

---

**سوال 67: Tool Selection Policy Enforcement**

**Pre-execution enforcement:**
1. Agent proposes tool selection → Gateway evaluates:
   - Is this tool allowed for this tenant/user?
   - Is this tool appropriate for this task? (e.g., using email sender for data analysis = suspicious)
   - Is a cheaper alternative available?

2. If denied → Gateway suggests substitute:
   - "Browser denied for stock data. Use stock-api tool instead (faster, cheaper, more accurate)"
   - Agent can accept substitute or request different tool

3. **Capability downgrade:**
   - Agent requests "code executor with network access"
   - Policy allows "code executor without network" (lower risk)
   - Gateway downgrades: "You can use code executor but no network access"
   - Agent adjusts plan accordingly

4. **Override:**
   - User can override Gateway's tool selection (with audit + risk acknowledgment)
   - Override requires: user signature, reason, risk acceptance
   - Override logged for security review

---

**سوال 68: Dynamic Tool Registration**

**Registration API:**
```
POST /tools/register
{
  "name": "custom-data-processor",
  "version": "1.0.0",
  "capabilities": ["data-processing", "ETL"],
  "description": "Processes CSV files and generates reports",
  "endpoint": "https://internal-tool.example.com/process",
  "auth_method": "API_KEY",
  "rate_limit": 100,
  "cost_per_call": 0.02
}
```

**Discovery:**
- Registered tools appear in Tool Registry
- Agents query registry: "What tools are available for data processing?"
- Registry returns: tool name, version, capabilities, cost, health status

**Versioning:**
- Semantic versioning: MAJOR.MINOR.PATCH
- Multiple versions can coexist: `custom-tool:1.0.0` and `custom-tool:1.1.0`
- Default: latest, but agents can specify version
- Deprecation: mark version as deprecated → 30-day sunset period → remove

**Health:**
- Health check: Gateway pings tool endpoint every 60s
- If unhealthy → mark as unavailable, route to alternatives
- Recovery: if healthy for 3 consecutive checks → mark available

---

**سوال 69: Tool Selection Based on Cost-Latency Trade-off**

**Decision framework:**
1. Agent has two options:
   - Fast tool: 200ms, $0.10 per call
   - Slow tool: 5s, $0.01 per call
2. **User preferences:**
   - "Speed priority" → use fast tool
   - "Cost priority" → use slow tool
   - "Balanced" → use fast if task is urgent, slow otherwise
3. **Runtime re-evaluation:**
   - If fast tool is overloaded (latency >2s) → switch to slow tool
   - If budget running low → switch to slow tool
4. **Learning:**
   - Track historical latencies for both tools
   - If fast tool consistently slow → reclassify as "slow"
   - Periodic re-evaluation of tool classification

**Decision logic:**
```
if (user_preference == "speed" || task_deadline < 1s):
    select(fast_tool)
elif (user_preference == "cost" || remaining_budget < threshold):
    select(slow_tool)
else:
    select(tool_with_best_cost_per_latency_ratio)
```

---

**سوال 70: Tool Selection Safety Constraints**

**Risk classification:**
| Risk Level | Tools | Additional Checks |
|---|---|---|
| Low | Browser (read), file read | Standard policy check |
| Medium | Code executor, file write | + Approval if batch > 10 |
| High | Email sender, database write | + Always approval |
| Critical | File delete, shell execution, database delete | + Two-person approval + break-glass option |

**Additional checks for high-risk tools:**
- **Behavioral anomaly:** Is agent using this tool unusually? (e.g., first time using email sender)
- **Rate check:** Is agent using this tool too frequently? (>5/min for email = suspicious)
- **Context check:** Does tool usage match agent's stated task? (e.g., email sender for "data analysis" task = suspicious)

**Circuit breaker:**
- Per tool: if error rate >50% in 5 min → circuit opens → block tool for 10 min
- Per agent: if agent has >3 tool violations in 1 hour → block agent
- Manual reset: admin can close circuit early after investigation

**Reasoning:** Dangerous tools unrestricted access = security disaster. Defense-in-depth: policy + approval + behavioral monitoring + circuit breaker۔

---

## Execution Plane (سوال 71 تا 140)

### Browser Gateway (سوال 71–78)

---

**سوال 71: Browser Gateway Architecture**

**Responsibilities:**
- Proxy between agents and isolated browser workers
- Session management (create, route, destroy)
- Request validation and sanitization
- Response filtering and size limiting
- Worker pool management (scaling, health)
- Audit logging of all browser operations

**Connection model:**
- Agent → Gateway: WebSocket (bidirectional, persistent)
- Gateway → Worker: WebSocket/CDP (Chrome DevTools Protocol)
- Gateway is stateless for routing (state in Redis), stateful for sessions

**Session persistence:**
- Session ID → worker mapping in Redis
- If Gateway restarts → sessions persist (worker continues, new Gateway reconnects)
- If worker dies → session lost → agent notified, can request new session

**Scaling:**
- Gateway: horizontal (stateless, behind LB)
- Workers: auto-scaling based on demand (CPU/memory metrics)
- Session affinity: sticky routing (same agent → same worker if possible)

---

**سوال 72: Browser Request Sanitization**

**URL filtering:**
1. **Allowlist/Denylist:** 
   - Allowlist: trusted domains (tenant-configurable)
   - Denylist: known malicious domains (phishing, malware)
2. **SSRF protection:**
   - Block: RFC 1918 private IPs (10.x, 172.16-31.x, 192.168.x)
   - Block: localhost, 0.0.0.0, metadata endpoints (169.254.169.254)
   - Block: internal service IPs (from Gateway's perspective)
3. **Protocol filtering:**
   - Allow: HTTP, HTTPS
   - Block: file://, ftp://, gopher://, data:// (exfiltration risks)

**Content-type filtering:**
- Allow: text/html, application/json, text/plain, images
- Block: application/octet-stream (unknown binary), executable types
- Configurable per tenant

**Header sanitization:**
- Strip: Authorization headers (prevent credential leak to external site)
- Strip: Cookie headers (prevent session leak)
- Inject: `X-Forwarded-For` with agent ID (for audit trail)

**Response sanitization:**
- Max response size: 10MB (configurable)
- Strip: Set-Cookie from external sites (prevent session fixation)
- Scan: response for known malware signatures (if malware scanning enabled)

---

**سوال 73: Browser Session Isolation**

**Isolation mechanisms:**
1. **Process-level isolation:** Each session = separate browser process (not just tab)
2. **Cookie/storage isolation:**
   - Each session has its own cookie jar
   - localStorage/sessionStorage/IndexedDB scoped per session
   - No shared cookies between agents
3. **Network isolation:**
   - Each worker has its own network namespace
   - No access to other workers' network traffic
   - Egress proxy: all traffic goes through filtering proxy
4. **Resource isolation:**
   - CPU: cgroup limit per worker (e.g., 1 CPU)
   - Memory: limit per worker (e.g., 512MB)
   - Disk: tmpfs per worker, size-limited

**Verification:**
- After session creation: verify no access to other sessions' data
- Periodic: attempt cross-session access → must fail

---

**سوال 74: Browser Rendering Pipeline**

**Rendering engine:**
- Chromium (headless) — industry standard, well-maintained
- CDP (Chrome DevTools Protocol) for programmatic control

**Optimization:**
1. **Lazy loading:** Don't render below-the-fold content unless needed
2. **Resource blocking:** Block images/videos if only text needed (configurable)
3. **DOM optimization:** Wait for DOM ready, not full page load (faster)
4. **JavaScript:** Execute but with timeout (5s max — prevent infinite loops)

**Screenshots:**
- On-demand: agent can request screenshot
- Automatic: on error (for debugging)
- Format: PNG, compressed, max resolution 1920x1080

**Content extraction:**
- After render: extract main content (not navigation, ads, etc.)
- Use: Readability.js or similar
- Output: clean HTML or plain text (agent's choice)

---

**سوال 75: Browser Automation**

**Automation protocol:**
- CDP (Chrome DevTools Protocol) — direct browser control
- Actions: click, type, scroll, navigate, wait
- All actions: logged with timestamp, target, result

**Action safety:**
- Pre-execution validation: is this action safe? (e.g., click on "Delete" button → approval?)
- Maximum actions per session: 100 (prevent runaway automation)
- Dangerous actions: form submission with POST → policy check

**Verification:**
- After action: verify expected result (e.g., "clicked login → now logged in?")
- If verification fails → retry (max 3) or abort

**Anti-bot detection:**
- Some sites have CAPTCHA/anti-bot → agent should detect and handle
- Strategy: if CAPTCHA encountered → notify user (can't solve automatically)
- Fingerprinting: use realistic user-agent, disable automation flags (limited — ethical considerations)

---

**سوال 76: Browser Content Extraction**

**Methods:**
1. **Readability extraction:** Main content only (remove nav, ads, sidebars)
2. **CSS selector-based:** Agent specifies selectors for targeted extraction
3. **LLM-based:** Render page → LLM extracts structured data
4. **Structured data detection:** JSON-LD, microdata, Open Graph

**Main content identification:**
- Heuristics: largest text block, semantic tags (`<article>`, `<main>`)
- ML-based: trained model to identify content vs chrome
- Readability.js: open-source, well-tested

**Structured data:**
- JSON-LD: parse and return as JSON
- Tables: extract HTML tables as CSV/JSON
- Forms: extract form structure (fields, types, options)

**Dynamic content:**
- Wait for: XHR/fetch requests to complete
- Scroll: trigger lazy-loaded content
- Timeout: 5s max for dynamic content

---

**سوال 77: Browser Security**

**Sandboxing:**
- **Container isolation:** Each browser worker in its own container (Docker + seccomp)
- **MicroVM:** For higher isolation — gVisor/Kata Containers
- **No host access:** Workers cannot access host filesystem, network, or processes
- **Verified:** Tencent Xuanwu Lab whitepaper confirms server-side browsers need defense-in-depth (static attack surface reduction + dynamic runtime isolation)

**Egress filtering:**
- All browser traffic through egress proxy
- Proxy enforces: URL filtering, rate limiting, data exfiltration detection
- No direct internet access from worker

**Malware protection:**
- Response scanning: ClamAV or similar for downloaded files
- Behavior monitoring: detect drive-by downloads, exploit attempts
- If malware detected → block, quarantine, alert

**Credential protection:**
- Credentials stored in encrypted vault (not in browser)
- Injected per-session via CDP
- Never persisted in browser cookies/localStorage
- Session end → credentials wiped

---

**سوال 78: Browser Performance**

**Resource per session:**
- CPU: 0.5-1 core
- Memory: 256-512MB
- Disk: 100MB (tmpfs)

**Pooling:**
- Warm pool: 10-20 pre-initialized browser instances (ready for immediate use)
- Cold start: ~3s (initialize browser), warm start: <100ms
- Pool sizing: based on historical peak demand + 20% buffer

**Memory management:**
- Memory leak detection: if worker memory >80% of limit → recycle
- Tab management: close unused tabs (>5 min idle)
- Garbage collection: force GC between sessions

**Caching:**
- HTTP cache: shared (read-only resources like CSS/JS libraries)
- DNS cache: per-worker, TTL 60s
- But: no cookie/cache sharing between sessions (isolation)

---

### Isolated Browser Worker (سوال 79–86)

---

**سوال 79: Browser Worker Isolation**

**Isolation technology:**
1. **Docker containers + seccomp:** Basic isolation, shared kernel
2. **gVisor:** Userspace kernel, intercepts syscalls — stronger isolation
3. **Kata Containers / Firecracker:** MicroVM — hardware-level isolation, separate kernel
4. **Recommended for GNW:** MicroVM (Firecracker) for untrusted content, Docker for trusted

**Verification:**
- Container escape tests (regularly)
- Kernel CVE monitoring (patch within 24h for critical)
- Runtime: seccomp profile blocks dangerous syscalls (clone, mount, etc.)

**Resource constraints:**
- CPU: cgroup limit
- Memory: cgroup limit + OOM killer
- Disk: tmpfs size limit
- Network: egress proxy only
- File descriptors: limit per process

**Breach response:**
1. Isolate worker (network cut)
2. Capture memory dump for forensics
3. Kill worker
4. Alert security team
5. Investigate: what was accessed? What was the payload?
6. Patch vulnerability
7. Deploy fixed worker image

---

**سوال 80: Browser Worker Lifecycle**

**Creation:**
1. Request from Gateway (new session needed)
2. Pool manager checks warm pool → if available, assign warm worker
3. If no warm worker → create new: pull image, start container, init browser
4. Worker registered in session store
5. Ready for use (~3s cold, <100ms warm)

**Health monitoring:**
- Heartbeat: every 10s, worker reports: CPU, memory, browser status
- If heartbeat missed 3x → mark unhealthy
- Health check: can browser navigate? Is CDP responsive?

**Termination:**
- Normal: session ends → worker returns to warm pool (for reuse)
- Unhealthy: kill worker, remove from pool
- Resource exhaustion: memory >80% → graceful shutdown (save state if possible)
- Max age: workers recycled after 4 hours (prevent memory leak accumulation)

**Recycling:**
1. Worker marked for recycling
2. Active session: allow to complete (max 5 min grace)
3. Clear all state: cookies, cache, localStorage
4. Return to warm pool OR destroy if too old

---

**سوال 81: Browser Worker Credential Management**

**Storage:**
- Credentials never stored in browser worker
- Stored in: encrypted vault (HashiCorp Vault or similar)
- Per-tenant encryption keys

**Injection:**
- When agent needs to log into a site:
  1. Gateway requests credential from vault
  2. Gateway injects via CDP: `Page.navigate` + `Input.insertText`
  3. Credential in memory only for duration of login
  4. After login: credential cleared from worker memory
  5. Browser session: authenticated via cookies (not stored credentials)

**Isolation:**
- Credentials scoped to specific session only
- No cross-session credential sharing
- Credential vault access: audited (who, what, when)

**Rotation:**
- Credentials rotated per tenant policy (e.g., every 90 days)
- When rotated: old credentials invalidated, new ones stored
- Active sessions: re-authenticate with new credentials

---

**سوال 82: Browser Worker Network**

**Topology:**
```
Agent → Gateway → Egress Proxy → [Worker] → Internet
                           ↑
                    DNS Filter + URL Filter
```

**Egress filtering:**
- All traffic through egress proxy (no direct internet)
- Proxy enforces: URL allowlist/denylist, SSRF protection
- Rate limiting: per-worker bandwidth limit (e.g., 10 Mbps)
- Data exfiltration detection: large outgoing transfers → alert

**DNS security:**
- DNS through filtered resolver (not worker's own)
- Block: known malicious domains (phishing, C2 servers)
- DNS over HTTPS (DoH) to prevent DNS hijacking
- DNS rebinding protection: validate resolved IP doesn't change between requests

**Monitoring:**
- All network requests logged: URL, method, size, status
- Anomaly: unusual traffic patterns (e.g., large upload to unknown server)
- Alert: data exfiltration patterns (large POST to external endpoint)

---

**سوال 83: Browser Worker State Management**

**State types:**
- **Cookies:** per-session, isolated, cleared on session end
- **localStorage/sessionStorage:** per-origin, per-session, cleared on session end
- **IndexedDB:** per-origin, per-session, cleared on session end
- **Cache (HTTP):** shared (read-only resources), not per-session

**Persistence:**
- Default: no persistence (state cleared between sessions)
- Optional: session state can be saved (for resume) — encrypted, stored in Redis
- Saved state: cookies + localStorage only (not IndexedDB — too large)

**Isolation:**
- Each session: separate browser profile (complete state isolation)
- No shared state between sessions
- Verification: attempt to read another session's cookies → must fail

**Cleanup:**
- On session end: clear all state immediately
- On worker recycle: full state wipe (destroy profile, create new)
- Periodic: verify no state leaked between sessions

**Migration:**
- If worker needs to move (maintenance): save state → create new worker → restore state
- State transfer: encrypted, authenticated channel

---

**سوال 84: Browser Worker File System**

**Isolation:**
- tmpfs per worker (in-memory filesystem)
- No access to host filesystem
- No access to other workers' filesystems
- Size limit: 100MB (configurable)

**Security:**
- No executable permission on downloaded files
- File type whitelist: .txt, .csv, .json, .html, .png, .jpg, .pdf
- Block: .exe, .sh, .bat, .dll, .so
- Malware scan: downloaded files scanned before use

**Size limits:**
- Per-file: 10MB
- Per-session total: 100MB
- If exceeded: error, agent must clear files or request larger quota

**Transfer:**
- Download: internet → worker tmpfs (via egress proxy, scanned)
- Upload: worker tmpfs → agent (via Gateway, size-limited)
- Worker → Worker: NOT allowed (isolation)
- Worker → External: NOT allowed (exfiltration prevention)

---

**سوال 85: Browser Worker Scaling**

**Triggers:**
- Scale-out: active sessions >80% of pool capacity
- Scale-in: active sessions <30% of pool capacity for 10 min
- Predictive: based on historical patterns (e.g., weekday morning spike)

**Speed:**
- Scale-out: 5 workers/min (prevent thundering herd on infrastructure)
- Warm pool maintained: always 10-20 ready workers
- Cold start: ~3s per worker

**Limits:**
- Min: 5 workers (always available)
- Max: 200 workers (per region, configurable)
- Hard cap: based on infrastructure capacity (CPU, memory)

**Over-provisioning:**
- Warm pool = 20% above current demand (ready for spikes)
- Cost: acceptable (browser workers are lightweight)
- Recycling: idle workers >30 min → destroy (save resources)

---

**سوال 86: Browser Worker Observability**

**Metrics:**
| Metric | Type |
|---|---|
| `active_browser_sessions` | Gauge |
| `browser_session_duration` | Histogram |
| `browser_request_latency` | Histogram |
| `browser_errors_total` | Counter (by type) |
| `worker_pool_size` | Gauge |
| `worker_pool_utilization` | Gauge (%) |
| `worker_recycle_count` | Counter |
| `browser_memory_usage` | Gauge (per worker) |

**Logs:**
- All browser requests (URL, method, status, duration)
- Worker lifecycle events (create, health, recycle, destroy)
- Security events (blocked URL, malware detected, egress violation)

**Tracing:**
- Per session: trace from agent → Gateway → worker → external site
- Useful for: latency debugging, error tracing

**Alerting:**
- High error rate: >5% of requests erroring → WARNING
- Pool exhaustion: utilization >95% → CRITICAL
- Memory: worker memory >80% → WARNING
- Security: malware detected → CRITICAL

---

### Code/Shell Sandbox (سوال 87–94)

---

**سوال 87: Code Sandbox Architecture**

**Technology:**
- **Primary:** MicroVM (Firecracker/gVisor) — hardware-level isolation
- **Secondary:** Docker + seccomp — for trusted, lower-risk code
- **Language runtime:** Python, Node.js, Bash, SQL (SQLite)

**Language support:**
- Python 3.x (most common for AI/ML)
- JavaScript/Node.js (web automation)
- Bash (system operations)
- SQL (read-only, SQLite only)

**Resource limits:**
| Resource | Limit | Enforcement |
|---|---|---|
| CPU | 1 core | cgroup |
| Memory | 512MB | cgroup + OOM killer |
| Disk | 100MB tmpfs | tmpfs size |
| Network | Egress proxy only | Network namespace |
| Execution time | 30s default, max 300s | Process timeout |
| File descriptors | 1024 | ulimit |

**Capability restrictions:**
- No filesystem access outside tmpfs
- No network access (except through proxy)
- No process spawning (except whitelisted)
- No kernel modules
- No hardware access

---

**سوال 88: Code Execution Safety**

**Multi-layer defense:**

1. **Static analysis (pre-execution):**
   - AST parsing: detect dangerous patterns (e.g., `os.system`, `subprocess.call`, `eval`)
   - Import analysis: block dangerous modules (`os`, `sys`, `subprocess`, `socket`)
   - String analysis: detect obfuscated code (base64-encoded payloads)
   - If dangerous → deny or require approval

2. **Runtime monitoring:**
   - Syscall monitoring: seccomp filter blocks dangerous syscalls
   - Network monitoring: all connections through proxy
   - File monitoring: no writes outside tmpfs
   - Process monitoring: no fork/exec (except whitelisted)

3. **Output sanitization:**
   - Output size limit: 1MB
   - ANSI escape codes stripped (prevent terminal manipulation)
   - No binary output (text only, unless explicitly requested)

4. **Code review (for persistent code):**
   - If agent writes code that persists (e.g., notebook) → human review required
   - Automated: linting, security scanning
   - Manual: if code accesses external resources or handles sensitive data

---

**سوال 89: Multi-Language Sandbox**

**Unified vs per-language:**
- **Recommendation:** Unified sandbox container with multiple runtimes
  - Pros: shared filesystem (pass data between languages), simpler management
  - Cons: larger image, more attack surface
- **Alternative:** Per-language containers
  - Pros: smaller attack surface per container
  - Cons: data transfer between containers needed

**Language-specific risks:**
| Language | Key Risks | Mitigations |
|---|---|---|
| Python | `os.system`, `subprocess`, `socket`, `pickle` | Import restrictions, seccomp |
| JavaScript | `require('child_process')`, eval, `fs` | Module restrictions, no `require` |
| Bash | Command injection, `$(...)`, pipes | Whitelist commands, no pipes to external |
| SQL | SQL injection, data exfiltration | Read-only, SQLite (no network), row limit |

**Versioning:**
- Multiple versions coexist: Python 3.10, 3.11, 3.12
- Agent specifies version in request
- Default: latest stable

**Package management:**
- Pre-installed: common packages (numpy, pandas, requests — verified)
- Custom packages: from approved registry only (no pip install from PyPI)
- If agent needs unapproved package → request + security review

---

**سوال 90: Code Execution Timeout**

**Timeout types:**
1. **Wall clock timeout:** Total execution time (e.g., 30s)
2. **CPU time timeout:** Actual CPU used (e.g., 10s CPU — catches infinite loops with sleep)
3. **I/O timeout:** Network/database operations (e.g., 5s per call)

**Enforcement:**
- Wall clock: `SIGTERM` at timeout, `SIGKILL` at timeout+5s
- CPU time: cgroup CPU quota (exceed → process throttled/killed)
- I/O: per-call timeout in proxy

**Graceful timeout:**
1. At T-5s: send warning to agent "approaching timeout"
2. At T: send SIGTERM (process can clean up)
3. At T+5s: send SIGKILL (force kill)
4. Clean up: kill child processes, release resources, return partial output

**Tuning:**
- Default: 30s (most tasks)
- Configurable: 5s-300s per request
- Long-running: separate execution plane (see Long-Running Tasks)

---

**سوال 91: Code Execution Resource Limits**

**Enforcement via cgroups:**
- **CPU:** `cpu.cfs_quota_us` / `cpu.cfs_period_us` — limit to 1 core
- **Memory:** `memory.limit_in_bytes` — 512MB, OOM killer on exceed
- **Disk:** tmpfs size mount — 100MB
- **Network:** network namespace + egress proxy
- **PIDs:** `pids.max` — 100 (prevent fork bomb)

**Hierarchy:**
- Parent cgroup: sandbox limits
- Child cgroup: per-process limits (if multi-process)
- Child cannot exceed parent limits

**Soft vs hard limits:**
- Soft (memory): warning at 80%, throttle at 90%
- Hard (memory): OOM kill at 100%
- Soft (CPU): throttle (reduce share)
- Hard (CPU): cannot exceed quota

**Monitoring:**
- Per-sandbox: CPU %, memory MB, disk MB, network bytes
- If approaching limits → alert agent (may need to optimize code)
- Metrics stored for post-execution analysis

---

**سوال 92: Code Execution Output**

**Capture:**
- stdout + stderr captured
- Return code captured
- Execution metadata: duration, resource usage, warnings

**Size limits:**
- stdout: 1MB max (truncated if exceeded, with notice)
- stderr: 256KB max
- If output exceeds limit: last 100KB kept + "output truncated" notice

**Streaming:**
- Long-running execution: stream output via WebSocket
- Agent receives output in real-time (no waiting for completion)
- If connection drops: buffer output, deliver on reconnect

**Format:**
- Default: text/plain
- Rich: JSON with stdout, stderr, returncode, metadata
- Binary: base64 encoded (if agent requests binary output, e.g., generated image)

---

**سوال 93: Code Execution Caching**

**Cache key:**
- `hash(code_content + language + version + input_data_hash + environment_config)`
- If same code + same input → same output → cache hit

**Granularity:**
- Full execution: cache entire output
- Partial: cache intermediate results (if code has multiple stages)

**Invalidation:**
- Code change: new hash → cache miss
- Input change: new hash → cache miss
- Environment change (e.g., package version) → cache miss
- TTL: 24 hours (configurable)

**Security:**
- Cache key doesn't include sensitive data (e.g., API keys)
- Cached output doesn't contain secrets (sanitized before caching)
- Per-tenant cache isolation (Tenant-A's cached results not served to Tenant-B)

---

**سوال 94: Shell Execution Safety**

**Command injection prevention:**
- Never use `eval()` or shell=True in subprocess
- All commands: explicit argument list (not string)
- User input: always quoted/escaped
- Metacharacters blocked: `;`, `|`, `&`, `$()`, backticks

**Dangerous commands:**
- **Blocked:** `rm -rf`, `dd`, `mkfs`, `shutdown`, `reboot`, `kill`, `pkill`
- **Blocked:** `wget`, `curl` (network access through proxy only)
- **Blocked:** `chmod 777`, `chown`, `mount`, `umount`
- **Whitelisted:** `ls`, `cat`, `grep`, `awk`, `sed`, `head`, `tail`, `wc`, `sort`, `uniq`

**Shell environment:**
- Restricted shell (rbash) or custom shell with command whitelist
- No environment variables with secrets
- PATH restricted to approved binaries only
- Working directory: tmpfs only

**Resource limits:**
- Same as code sandbox (CPU, memory, disk, network, time)
- Additional: max command length (4KB), max arguments (100)

---

### File Execution Layer (سوال 95–102)

---

**سوال 95: File System Architecture**

**Model:**
- Virtual filesystem per agent/user
- Backend: object storage (S3/OSS) for blobs + metadata DB for structure
- Path-based access: `/tenant_id/user_id/project_name/file.txt`

**Access control:**
- Every file access: policy check (read/write/delete)
- Path-based: which directories accessible?
- Operation-based: read-only vs read-write
- Context-based: time-of-day, agent identity

**Operations:**
- CRUD: create, read, update, delete
- Move/rename (within same tenant)
- Copy (within same tenant)
- Share (cross-agent, with permission)

**Backend:**
- Hot tier: SSD-backed (active files, fast access)
- Cold tier: object storage (archived files, cheaper)
- Auto-tiering: files not accessed in 30 days → cold tier

---

**سوال 96: File Access Control**

**Rule types:**
1. **Path-based:** `/shared/reports/*` → all agents in tenant can read
2. **Operation-based:** `read` allowed, `write` requires approval, `delete` requires two-person approval
3. **Context-based:** `write` only during business hours, `delete` only from office IP range

**Evaluation:**
1. Extract: agent_id, file_path, operation
2. Policy: match path patterns → applicable rules
3. Evaluate: operation allowed? Context met?
4. If multiple rules match: most restrictive wins (deny precedence)

**Enforcement:**
- Every file operation goes through File Gateway
- Gateway: policy check → allow/deny → execute or reject
- No direct backend access (Gateway is the only path)

---

**سوال 97: File Versioning**

**Model:**
- Every write creates a new version (not overwrite)
- Version history: immutable, append-only
- Current version = latest
- Old versions: accessible, read-only

**Storage:**
- Content-addressable: hash of content = storage key
- Identical content: deduplicated (same hash = same blob)
- Metadata: version number, timestamp, author, size, hash

**Management:**
- Max versions per file: 100 (configurable)
- Old versions auto-pruned: keep first, last, and every 10th
- Storage cost: deduplication reduces ~60% for typical workloads

**Rollback:**
- Agent can request rollback to any version
- Rollback = create new version with old content (not delete newer versions)
- Rollback audited

---

**سوال 98: File Sharing**

**Model:**
- Share = permission grant for another agent to access file
- Types: read-only, read-write
- Scope: specific file or directory

**Permissions:**
- Owner: full control
- Shared with: as granted (read-only or read-write)
- Others: no access

**Lifecycle:**
- Share created: owner grants access
- Share expires: TTL (e.g., 7 days) or explicit revocation
- Share revoked: owner revokes → immediate access removal

**Security:**
- Cross-tenant sharing: requires both tenants' admin approval
- Shared file access: audited (who accessed, when, what operation)
- Watermarking: optional, for confidential files

---

**سوال 99: Large File Handling**

**Upload:**
- Chunked upload: file split into 5MB chunks
- Resumable: if connection drops, resume from last chunk
- Parallel: multiple chunks uploaded simultaneously
- Progress: real-time progress to agent

**Processing:**
- Streaming: process file in chunks (not load entire file into memory)
- MapReduce: for very large files, distribute processing
- Example: 10GB CSV → chunk into 100MB blocks → process in parallel

**Storage:**
- Multipart storage: large files stored as parts in object storage
- Assembly: on read, parts reassembled transparently
- Tiering: large files → cold storage (cheaper for large volumes)

**Transfer:**
- Agent → Gateway: chunked, size-limited per chunk
- Gateway → Worker: streaming (not buffered)
- Size limits: configurable per tenant (default: 5GB max file size)

---

**سوال 100: File Execution Environment**

**Execution model:**
1. **Scripts:** Python/JS files → execute in code sandbox (see Q87-94)
2. **Notebooks:** Jupyter notebooks → execute in notebook sandbox
   - Cell-by-cell execution
   - State persists between cells (within session)
   - Output: inline (text, images, tables)
3. **Binaries:** Pre-compiled binaries → execute in restricted sandbox
   - Binary must be from trusted source (signed/verified)
   - No arbitrary binary execution (security risk)

**Notebook execution:**
- Kernel: Python 3 (default), configurable
- State: in-memory (per session), not persisted
- Output: captured, size-limited
- Timeout: 300s per cell

**Script execution:**
- Same as code sandbox (Q87-94)
- File path → read content → execute in sandbox
- Output captured and returned

**Binary execution:**
- Only pre-approved binaries (from Tool Registry)
- In microVM sandbox (strongest isolation)
- Full audit logging

---

**سوال 101: File Search and Indexing**

**Metadata search:**
- Fields: filename, author, tags, creation date, modification date, size
- Query: SQL-like (`WHERE author = 'agent-1' AND tags CONTAINS 'report'`)
- Fast: indexed in metadata DB

**Full-text search:**
- Elasticsearch index of file content
- Query: full-text (`"Q3 sales report"`)
- Near real-time indexing (delay < 5s)

**Semantic search:**
- Embed file content → vector DB
- Query: "Find files about financial performance" → semantic match
- More powerful than keyword (understands meaning)

**Security:**
- Search results: only files agent has access to (policy-filtered)
- No leaking of file existence to unauthorized agents
- Search query itself: logged (for audit)

---

**سوال 102: File Backup and Recovery**

**Strategy:**
- **RPO (Recovery Point Objective):** 1 hour (max 1 hour data loss)
- **RTO (Recovery Time Objective):** 15 min (restore within 15 min)

**Backup:**
- Continuous: incremental backups every 15 min (log-based)
- Daily: full snapshot at 2 AM
- Weekly: full backup to cold storage (cross-region)

**Storage:**
- Hot backup: same region, SSD (fast restore)
- Cold backup: cross-region, object storage (disaster recovery)
- Retention: daily backups 30 days, weekly 1 year, monthly 7 years

**Recovery:**
- File-level: restore specific file from backup
- Volume-level: restore entire directory/project
- Cross-region: if primary region down → restore from cold backup

**Testing:**
- Monthly: restore test (verify backup integrity)
- Quarterly: disaster recovery drill (full restore to staging)
- Annual: cross-region failover test

---

### Web Research Pipeline (سوال 103–110)

---

**سوال 103: Web Research Architecture**

**Stages:**
1. **Query Formulation:** Research task → search queries
2. **Search Execution:** Queries → search engine results (via Browser Gateway)
3. **Content Extraction:** Result pages → clean content
4. **Synthesis:** Multiple sources → coherent answer
5. **Quality Check:** Verify answer quality, cite sources
6. **Iteration:** If insufficient → refine queries, repeat

**Orchestration:**
- DAG (Directed Acyclic Graph) of stages
- Parallel: multiple searches simultaneously
- Sequential: extraction depends on search results
- Feedback: quality check → iterate if needed

**State:**
- Research session: all queries, results, extractions, synthesis
- Persisted: for resumption if interrupted
- Audit: full trail for transparency

**Feedback loop:**
- If synthesis quality < threshold → return to query formulation with refined queries
- If sources conflicting → additional searches to resolve
- If insufficient information → notify user with what was found

---

**سوال 104: Search Query Formulation**

**Decomposition:**
1. Task: "What are the latest trends in AI agent security?"
2. Decompose: "AI agent security trends 2024", "LLM security vulnerabilities", "agent orchestration security"
3. Sub-queries: parallel search for each

**Optimization:**
- Keyword extraction: identify key terms
- Synonym expansion: "security" → "vulnerability", "threat", "risk"
- Site-specific: "site:arxiv.org AI agent security" (for academic)
- Time filter: "after:2024-01-01" (for recency)

**Multi-language:**
- If topic has more content in another language → search in that language
- Example: "AI research" → search English + Chinese (more sources)

**Evaluation:**
- Query quality metrics: result relevance, result count, source diversity
- If query returns <5 relevant results → reformulate

---

**سوال 105: Multi-Source Search**

**Source diversity:**
- General web (Google, Bing)
- Academic (Google Scholar, Semantic Scholar)
- Social media (Reddit, Twitter — for sentiment/trends)
- News (Google News, Bing News)
- Domain-specific (GitHub, Stack Overflow)

**Selection:**
- Based on task type: academic → Scholar, coding → GitHub, news → News
- Multiple sources: always use 2+ for diversity

**Deduplication:**
- URL-based: same URL from different sources → merge
- Content-based: similar content → keep most authoritative
- Title + snippet: near-duplicate detection

**Credibility:**
- Source authority: .gov > .edu > established news > blogs > forums
- Author: identified expert > anonymous
- Recency: recent > old (for trends)
- Cross-reference: if only 1 source → lower confidence

---

**سوال 106: Content Extraction and Cleaning**

**Extraction:**
1. Fetch page via Browser Gateway
2. Render: execute JavaScript (for SPA content)
3. Extract: Readability.js → main content
4. Parse: HTML → structured format (title, body, metadata)

**Cleaning:**
- Remove: navigation, ads, sidebars, footers
- Remove: scripts, styles, HTML entities
- Normalize: whitespace, encoding
- Strip: tracking pixels, analytics scripts

**Format handling:**
- HTML: standard extraction
- PDF: pdf.js → text extraction
- JSON: parse directly
- Images: OCR if text extraction needed

**Quality:**
- If extracted content <100 chars → likely extraction failure → flag
- If content looks like error page → flag, retry
- Language detection: verify content language matches query language

---

**سوال 107: Research Synthesis**

**Approach:**
1. Collect: all extracted content from multiple sources
2. Cluster: group by sub-topic (e.g., "security threats", "mitigations", "case studies")
3. Synthesize: LLM generates coherent summary per cluster
4. Integrate: combine cluster summaries into overall answer
5. Cite: every claim attributed to source(s)

**Conflict resolution:**
- If sources disagree → present both views with attribution
- Confidence: more sources = higher confidence
- Recency: newer sources preferred for factual claims
- Authority: more authoritative source preferred

**Citation:**
- Inline: "[1]" references to source list
- Source list: numbered, with URL, title, author, date, access date
- Confidence indicator: per-claim (high/medium/low based on source agreement)

**Confidence:**
- High: 3+ independent authoritative sources agree
- Medium: 2 sources or 1 authoritative
- Low: 1 non-authoritative source → flag as "unverified"

---

**سوال 108: Research Iteration**

**Iteration triggers:**
1. Insufficient results (<3 relevant sources)
2. Conflicting information (can't resolve with current sources)
3. Outdated information (all sources >1 year old)
4. Shallow coverage (sources don't answer specific aspects)
5. Quality check failure (synthesis score < threshold)

**Strategy:**
- Refine: modify queries (more specific, different terms)
- Expand: search additional sources, different languages
- Deep-dive: follow links from found sources (breadth-first)
- Pivot: reframe the question from different angle

**Budget:**
- Max iterations: 5 (configurable)
- Budget per iteration: tracked (browser calls, LLM tokens)
- If budget exhausted → return best available answer with caveats

**Learning:**
- Track: which query strategies work best
- Feedback: if user rates answer as helpful → reinforce those strategies
- Adaptive: future research uses successful patterns

---

**سوال 109: Research Quality Evaluation**

**Quality dimensions:**
1. **Relevance:** Does answer address the question?
2. **Accuracy:** Are facts correct? (cross-reference)
3. **Completeness:** Are all aspects covered?
4. **Currency:** Is information up-to-date?
5. **Source quality:** Are sources authoritative?
6. **Coherence:** Is the answer well-structured?
7. **Citation:** Are claims properly cited?

**Automated evaluation:**
- LLM as judge: prompt LLM to evaluate answer on each dimension (1-10)
- Source count: >5 sources = good
- Source diversity: >3 different domains = good
- Recency: average source age <6 months = good

**Human evaluation:**
- Sample 10% of research outputs for human review
- Reviewers rate on same dimensions
- Inter-rater reliability: track agreement

**Improvement:**
- Low-scoring outputs: analyze root cause → improve pipeline
- A/B testing: try different synthesis prompts, compare quality

---

**سوال 110: Research Pipeline Observability**

**Metrics:**
| Metric | Type |
|---|---|
| `research_tasks_total` | Counter |
| `research_task_duration` | Histogram |
| `search_queries_per_task` | Histogram |
| `sources_per_task` | Histogram |
| `research_quality_score` | Histogram |
| `research_iterations` | Histogram |
| `extraction_failure_rate` | Gauge |
| `synthesis_latency` | Histogram |

**Tracing:**
- Full pipeline trace: query → search → extract → synthesize → quality check
- Each stage: span with duration, input size, output size
- Bottleneck identification: which stage takes longest?

**Quality metrics:**
- Source diversity score
- Citation coverage (% claims with citations)
- Confidence distribution (high/medium/low)

**Debugging:**
- If quality score low → drill down: which stage failed?
- If extraction failure → which URL? Why?
- If synthesis poor → which sources? What conflicts?

---

### Long-Running Task Workers (سوال 111–118)

---

**سوال 111: Long-Running Task Architecture**

**Key differences from short-lived tasks:**
- Duration: minutes to hours (not seconds)
- State: must persist across restarts
- Resources: held for long duration
- Failure: expensive (can't just retry from start)

**Submission:**
1. Agent submits task: description, estimated duration, priority
2. Gateway validates: budget, policy, resources available
3. Task queued with unique task_id
4. Worker picks up task → starts execution
5. State persisted: every checkpoint

**State machine:**
```
SUBMITTED → QUEUED → ASSIGNED → RUNNING → CHECKPOINTING → 
  COMPLETED | FAILED | CANCELLED | TIMEOUT
```

**Persistence:**
- Task state: durable store (PostgreSQL)
- Checkpoints: object storage (S3)
- Logs: streaming to log store

**Isolation:**
- Each task in separate worker (no shared state)
- Resources: dedicated cgroup
- Network: isolated namespace

---

**سوال 112: Task Progress Tracking**

**Model:**
- Task has: `progress` (0-100%), `current_step`, `total_steps`, `estimated_completion`
- Progress updated by worker at each step

**Reporting:**
- Agent polls: GET /tasks/{id}/progress → returns progress
- Push: WebSocket/SSE for real-time updates
- Granularity: update every 5% or every 30s (whichever first)

**Estimation:**
- Initial: based on task type + estimated duration (from agent)
- Runtime: `(elapsed_time / progress) * remaining_progress`
- If progress stalled (>5 min no update) → flag as potentially stuck

**Visualization:**
- Progress bar (0-100%)
- Step list (completed, current, pending)
- Time: elapsed, estimated remaining
- Logs: recent log lines (for debugging)

---

**سوال 113: Task Timeout and Deadline**

**Types:**
1. **Wall clock timeout:** Max total duration (e.g., 4 hours)
2. **Inactivity timeout:** No progress for 15 min → timeout
3. **Step timeout:** Each step has own timeout
4. **User deadline:** User specifies "must complete by 5 PM"

**Behavior:**
- On timeout: graceful cancellation (see Q157-162)
- Partial results: saved if available
- Notification: agent + user notified

**Deadline negotiation:**
- If task can't meet deadline → worker estimates: "Can complete in 6h, deadline is 4h"
- Options: simplify task, allocate more resources, or reject

**SLA tracking:**
- Per task type: target completion time (e.g., "web research: <30 min")
- Actual vs target → SLA breach metrics
- If SLA breached >10% → capacity issue

---

**سوال 114: Task Prioritization**

**Priority model:**
- P0 (critical): production incident → preempt others
- P1 (high): user-facing deadline
- P2 (normal): standard task
- P3 (low): background/batch

**Priority inversion prevention:**
- If P3 task holds resource needed by P0 → P3 preempted
- Resource released to P0

**Starvation prevention:**
- Aging: P3 task waiting >1 hour → boost to P2
- Fair share: each tenant guaranteed minimum throughput

**Preemption:**
- P0 preempts P2 → P2 task checkpointed + paused
- P0 completes → P2 resumes from checkpoint
- Preemption audited (don't preempt same task repeatedly)

---

**سوال 115: Task Dependency**

**Model:**
- DAG: tasks can depend on other tasks
- `task_A depends_on [task_B, task_C]`
- Task A starts only after B and C complete

**Resolution:**
- On submission: parse dependencies
- Queue: only tasks with all dependencies completed are schedulable
- Circular dependency: detect + reject at submission

**Failure:**
- If task B fails → task A is "dependency failed" → cancelled (or rerun B)
- Configurable: `on_dependency_failure: cancel | retry_dependency | proceed_without`

**Monitoring:**
- Dependency graph visualization
- Blocked tasks: waiting on dependency → show what they're waiting for
- Critical path: longest dependency chain (determines total time)

---

**سوال 116: Task Scheduling**

**Algorithm:**
1. Filter: eligible tasks (dependencies met, budget available)
2. Sort: priority (P0 first), then deadline (earliest first), then age (oldest first)
3. Match: task requirements vs worker capabilities
4. Assign: highest-priority eligible task to best-matching worker

**Constraints:**
- Worker capacity: CPU, memory, GPU (if needed)
- Task requirements: language runtime, tool access, network
- Affinity: prefer same-region worker (lower latency)
- Anti-affinity: spread tasks across workers (fault tolerance)

**Optimization:**
- Bin packing: maximize worker utilization
- Gang scheduling: tasks needing multiple workers scheduled together
- Preemption: high-priority can preempt low-priority (with checkpoint)

**Observability:**
- Queue depth (by priority)
- Worker utilization
- Scheduling latency (time from submission to assignment)
- Preemption frequency

---

**سوال 117: Task Migration**

**Types:**
1. **Voluntary:** Worker maintenance → migrate task
2. **Forced:** Worker failure → migrate task
3. **Optimization:** Better worker available → migrate for performance

**State transfer:**
- Checkpoint: save current state
- Transfer: checkpoint to new worker
- Restore: new worker loads checkpoint
- Resume: continue from checkpoint point

**Triggers:**
- Worker health degraded → proactive migration
- Worker memory >90% → migrate to avoid OOM
- Better worker available → optimize (rare, expensive)

**Downtime:**
- Migration time = checkpoint time + transfer time + restore time
- Typical: 30-60s
- Agent notified: "Task migrating, brief pause"

---

**سوال 118: Task Worker Health**

**Health signals:**
1. **Heartbeat:** Worker reports every 30s (CPU, memory, task progress)
2. **Task progress:** If no progress in 5 min → unhealthy
3. **Error rate:** >50% errors in 5 min → unhealthy
4. **Resource usage:** CPU >95% or memory >90% for >5 min → overloaded
5. **Log output:** No log output in 5 min → possibly stuck

**Health checks:**
- Liveness: is worker process alive? (heartbeat)
- Readiness: can worker accept new tasks? (resources available)
- Deep: can worker actually execute? (test task every 5 min)

**Response:**
- Unhealthy: don't assign new tasks, investigate
- Stuck task: checkpoint + restart on new worker
- Failed worker: tasks migrated, worker recycled

**History:**
- Per-worker health history (last 24h)
- Failure patterns: if worker fails repeatedly → hardware issue?
- Capacity planning: healthy worker utilization → scale decisions

---

### Memory System (سوال 119–126)

---

**سوال 119: Memory Architecture**

**Multi-tier system:**
```
Tier 1: Working Memory (context window)
  ← Current task context, recent messages
  ← Capacity: 4K-200K tokens, latency: ~0ms

Tier 2: Session Memory (Redis)
  ← Current conversation history
  ← Capacity: unlimited, latency: ~1ms

Tier 3: Short-term Memory (LLM summary)
  ← Compressed summaries of recent sessions
  ← Capacity: limited, latency: ~1ms (cached)

Tier 4: Long-term Memory (Vector DB)
  ← Encoded experiences, facts, patterns
  ← Capacity: unlimited, latency: ~10-50ms
```

**Storage:**
- Tier 1: in-process (LLM context)
- Tier 2: Redis (fast, volatile)
- Tier 3: Redis + LLM-generated (compressed)
- Tier 4: Vector DB (Pinecone, Milvus, Weaviate)

**Access:**
- Tier 1: always in context (no retrieval needed)
- Tier 2: fetched on demand (session ID lookup)
- Tier 4: semantic search (similarity query)

**Isolation:**
- Per-agent: each agent has own memory space
- Per-tenant: tenant-level isolation (no cross-tenant memory access)
- Per-user: user-specific memories isolated from other users

---

**سوال 120: Memory Retrieval**

**Methods:**
1. **Semantic search:** Query embedding → vector DB similarity search → top-K memories
2. **Keyword search:** BM25/keyword index → exact matches
3. **Hybrid:** semantic + keyword → merge results (better recall)
4. **Temporal:** "memories from last week" → time-filtered
5. **Graph:** follow memory links (e.g., "mentioned in" relationships)

**Relevance:**
- Similarity score (cosine similarity for vector, BM25 for keyword)
- Recency boost: more recent memories slightly preferred
- Importance score: user-tagged or system-scored
- Context match: memory relevant to current task type

**Optimization:**
- Cache: frequent queries cached (LRU)
- Pre-fetch: based on task prediction, pre-load likely memories
- Batch: multiple retrievals in one vector DB query

**Context window:**
- Retrieved memories: fit into remaining context window
- If too many → rank by relevance, truncate
- Summary: if memories too large → LLM summarizes before injection

---

**سوال 121: Memory Encoding**

**What to encode:**
- **Facts:** "User's company is Acme Corp" (user preferences, identity)
- **Experiences:** "Tried approach X, it failed because Y" (lessons learned)
- **Decisions:** "Chose tool A over B because..." (decision rationale)
- **Context:** "In this project, 'report' means financial summary" (project-specific definitions)

**Format:**
- Structured: JSON with fields (type, content, timestamp, importance, tags)
- Embedding: content → embedding vector (for semantic search)
- Metadata: author, task context, related entities

**Timing:**
- **Immediate:** Critical facts (user identity, preferences) → encode immediately
- **End of session:** Session summary → encode after session ends
- **Periodic:** Consolidation (see Q122) → weekly

**Quality:**
- Deduplication: don't encode if similar memory already exists
- Verification: cross-check with existing memories (consistency)
- Importance scoring: high importance = always encode, low = maybe skip

---

**سوال 122: Memory Consolidation**

**Triggers:**
- Daily: consolidate previous day's session memories
- Threshold: when raw memories exceed 1000 entries → consolidate
- Idle: when agent idle → background consolidation

**Operations:**
1. **Merge:** Combine related memories ("User likes Python" + "User likes pandas" → "User prefers Python with pandas for data analysis")
2. **Summarize:** Multiple detailed memories → compressed summary
3. **Extract patterns:** "User asked about X 5 times" → "User frequently interested in X"
4. **Resolve conflicts:** If old memory contradicts new → keep new, archive old

**Priorities:**
- High importance: consolidate first
- Old + low importance: candidate for forgetting
- Contradictory: resolve before consolidating

**Verification:**
- After consolidation: verify no information loss (consolidated memory covers all original facts)
- Spot check: sample consolidated memories, verify against originals

---

**سوال 123: Memory Forgetting**

**Criteria:**
1. **Age:** Memories older than 1 year (configurable) → forget
2. **Low relevance:** Never retrieved in 6 months → forget
3. **Low importance:** System-scored low importance → forget
4. **Contradiction:** Superseded by newer memory → archive old
5. **User request:** GDPR "right to be forgotten" → delete

**Mechanism:**
- Soft delete: mark as "forgotten" (still in DB but not retrieved)
- Hard delete: permanently remove (after soft delete + 30-day grace period)
- Archive: move to cold storage (in case needed for audit)

**Schedule:**
- Weekly: evaluate candidates for forgetting
- Monthly: execute forgetting (batch delete)
- User-initiated: immediate

**Impact:**
- Forgetting should be transparent: agent doesn't know what it forgot
- If forgotten memory was important → system learns (user feedback → re-encode with higher importance)

---

**سوال 124: Memory Sharing**

**Model:**
- Shared memory space: per-project or per-team
- Agents in same project can access shared memories
- Types: facts (project context), experiences (shared lessons), patterns (best practices)

**Permissions:**
- Read: all agents in project
- Write: agent who created + project admin
- Delete: project admin only

**Quality:**
- Shared memories: higher importance threshold (don't share trivia)
- Verification: shared memory must be verified before sharing
- Conflict: if agent's private memory conflicts with shared → flag

**Conflicts:**
- If Agent-A's private memory contradicts shared memory → don't auto-overwrite
- Flag: "Private memory conflicts with shared memory: which is correct?"
- Resolution: user or admin decides

---

**سوال 125: Memory Privacy**

**PII detection:**
- Automated: NLP model detects PII in memories (names, emails, phone numbers, SSNs)
- On detection: mask or encrypt PII fields
- Configurable: per-tenant PII rules (what counts as PII)

**Handling:**
- PII memories: encrypted with user-specific key
- Access: only the user's agents can decrypt
- Sharing: PII memories cannot be shared cross-agent

**User access:**
- User can view all their memories (transparency)
- User can delete specific memories (GDPR right to erasure)
- User can export all memories (GDPR data portability)

**Audit:**
- All memory access logged
- PII access: elevated logging (who, what, when, why)
- Periodic audit: verify no unauthorized PII access

---

**سوال 126: Memory Performance**

**Storage scaling:**
- Vector DB: sharding by tenant_id (each tenant's vectors in own shard)
- Horizontal scaling: add shards as needed
- Index: HNSW (hierarchical navigable small world) — fast approximate search

**Retrieval performance:**
- Target: p99 <50ms for top-10 retrieval
- Optimization: ANN (approximate nearest neighbor) instead of exact
- Cache: frequent queries cached (hit rate target: 60%)

**Write performance:**
- Target: p99 <20ms for single memory write
- Batch: writes buffered and flushed in batches (every 100ms)
- Index update: asynchronous (don't block write on index update)

**Cost optimization:**
- Compression: embeddings quantized (float32 → int8) — 4x storage reduction
- Tiering: hot memories (recent, frequently accessed) → fast storage; cold → cheap storage
- Deduplication: similar embeddings deduplicated

---

### Model Router (سوال 127–132)

---

**سوال 127: Model Router Architecture**

**Routing criteria:**
1. Task complexity: simple (use small/cheap model), complex (use large/expensive model)
2. Latency requirement: real-time → fast model, batch → slow model OK
3. Cost budget: low budget → cheap model
4. Language: specific language → model with best language support
5. Context length: long context → model with large context window

**Catalog:**
```json
{
  "models": [
    {"id": "gpt-4o", "tier": "premium", "cost_per_1k_tokens": 0.01, "max_context": 128000},
    {"id": "gpt-4o-mini", "tier": "standard", "cost_per_1k_tokens": 0.001, "max_context": 128000},
    {"id": "local-llama-8b", "tier": "economy", "cost_per_1k_tokens": 0.0001, "max_context": 8000}
  ]
}
```

**Strategy:**
- Default: cheapest model that can handle the task
- Escalation: if model fails → escalate to more capable model
- Caching: if same prompt seen before → return cached response

**Fallback:**
- Primary model down → fallback to secondary
- Fallback chain: premium → standard → economy → error

---

**سوال 128: Model Selection Logic**

**Task analysis:**
1. Extract: prompt length, complexity indicators (code? reasoning? creative?)
2. Classify: simple classification / complex reasoning / code generation / creative writing
3. Score: each model scored on: capability match, cost, latency

**Scoring:**
```
score = (capability_match * 0.5) + (1 - cost_normalized) * 0.3 + (1 - latency_normalized) * 0.2
```
- Highest score = selected model

**Multi-model orchestration:**
- Sometimes use multiple models:
  - Model A (small) for initial classification
  - Model B (large) for complex reasoning
  - Model C (specialized) for code generation
- Pipeline: A → B → C as needed

**Audit:**
- Every model selection logged: task, selected model, score, alternatives considered
- Enables post-hoc analysis: "Why was expensive model used for simple task?"

---

**سوال 129: Model Load Balancing**

**Algorithm:**
- Weighted round-robin: distribute based on model capacity
- Least connections: route to instance with fewest active requests
- Health-aware: skip unhealthy instances

**Health:**
- Liveness: HTTP health check every 10s
- Readiness: can accept requests? (not overloaded)
- Error rate: >5% errors in 1 min → mark degraded

**Rate limiting:**
- Per-model rate limit (API provider's limit)
- Per-tenant rate limit (tenant fairness)
- Per-agent rate limit (prevent runaway agent)

**Cross-region:**
- If primary region's model instances overloaded → route to secondary region
- Latency trade-off: secondary region adds ~50ms but prevents timeout
- Failover: if primary region completely down → all traffic to secondary

---

**سوال 130: Model Cost Optimization**

**Cost hierarchy:**
1. Cache hit (free) → always try first
2. Economy model ($0.0001/1K) → simple tasks
3. Standard model ($0.001/1K) → medium tasks
4. Premium model ($0.01/1K) → complex tasks only

**Task-appropriate selection:**
- "Summarize this text" → economy model (simple task)
- "Write a Python data pipeline" → standard model (code generation)
- "Analyze legal contract for risks" → premium model (complex reasoning)

**Cascading:**
- Try economy model first
- If response quality low → escalate to standard
- If still low → escalate to premium
- Quality check: confidence score on response

**Tracking:**
- Per-agent: total cost, cost by model tier
- Per-task: cost breakdown by model usage
- Optimization: weekly report: "Agent X used premium model 80% of time for simple tasks → adjust routing"

---

**سوال 131: Model Quality Monitoring**

**Metrics:**
1. **Response quality:** LLM-as-judge score (1-10)
2. **Error rate:** % responses with errors (syntax, logic, hallucination)
3. **User feedback:** thumbs up/down on responses
4. **Task success rate:** did the task complete successfully?
5. **Latency trend:** is model getting slower?

**Degradation detection:**
- Rolling 7-day average quality vs baseline
- If quality drops >10% → model degradation suspected
- Possible causes: model version change, prompt regression, data drift

**Quality-based routing:**
- If model A's quality drops → route more to model B
- Automatic: degradation detected → reduce traffic to degraded model
- Recovery: if quality recovers → restore normal routing

**Feedback loop:**
- User feedback → model routing adjustment
- "Users prefer model A for code tasks" → increase model A weight for code tasks
- Continuous learning from feedback

---

**سوال 132: Model Router Observability**

**Metrics:**
| Metric | Type |
|---|---|
| `model_requests_total` | Counter (by model, tenant) |
| `model_cost_total` | Counter (by model, tenant) |
| `model_latency` | Histogram (by model) |
| `model_error_rate` | Gauge (by model) |
| `model_quality_score` | Histogram |
| `cache_hit_rate` | Gauge |
| `routing_decisions` | Counter (by selected model) |

**Decisions log:**
```
{
  "timestamp", "agent_id", "task_type", "prompt_length",
  "selected_model", "alternatives": [...], "scores": [...],
  "actual_cost", "actual_latency", "quality_score"
}
```

**Dashboards:**
- Cost dashboard: per-tenant, per-model, daily/monthly trends
- Quality dashboard: model comparison, degradation alerts
- Latency dashboard: p50/p95/p99 per model
- Routing dashboard: decision distribution, escalation rate

---

### Tool Registry (سوال 133–136)

---

**سوال 133: Tool Registry Architecture**

**Schema:**
```json
{
  "tool_id": "uuid",
  "name": "web-search",
  "version": "2.1.0",
  "description": "Search the web for information",
  "capabilities": ["search", "web-access"],
  "input_schema": {...},
  "output_schema": {...},
  "endpoint": "https://...",
  "auth": "API_KEY",
  "cost_per_call": 0.05,
  "rate_limit": 100,
  "risk_level": "low",
  "health_status": "healthy"
}
```

**Discovery:**
- Agents query: "What tools can do web search?" → registry returns matches
- Capabilities-based search (not name-based)
- Version availability: which versions are active?

**Lifecycle:**
- Registered → Active → Deprecated → Retired
- Deprecation: 30-day notice, agents must migrate
- Retirement: tool removed from registry, calls fail

**Validation:**
- On registration: validate schema, test endpoint, security scan
- Periodic: health checks (every 60s), schema validation
- On update: version comparison, backward compatibility check

---

**سوال 134: Tool Versioning**

**Versioning scheme:**
- Semantic versioning: MAJOR.MINOR.PATCH
  - MAJOR: breaking changes (new required params, removed output fields)
  - MINOR: new features (optional params, new output fields)
  - PATCH: bug fixes (no API change)

**Resolution:**
- Agent specifies version: `web-search:2.1.0` → exact
- Agent specifies range: `web-search:2.x` → latest 2.x
- Agent specifies nothing: `web-search` → latest stable

**Deprecation:**
- Old version marked deprecated → 30-day sunset
- During sunset: still available, but warnings logged
- After sunset: version removed, calls fail with "version retired, upgrade to X.Y.Z"

**Rollback:**
- If new version causes issues → mark as "unstable"
- Previous stable version remains active
- Agents automatically routed to previous stable

---

**سوال 135: Tool Capability Description**

**Ontology:**
- Capabilities: hierarchical (e.g., `web-access` → `web-search` → `web-search-text`)
- Each capability: description, input requirements, output format
- Cross-references: "web-search" relates to "data-retrieval"

**Matching:**
- Agent describes needed capability → registry matches to tools
- Fuzzy matching: if exact capability not found → suggest closest
- Multi-capability: tool that has multiple capabilities

**Constraints:**
- Input schema: what parameters required
- Output schema: what format returned
- Preconditions: what must be true (e.g., "requires network access")
- Postconditions: what changes after execution

**Evolution:**
- New capabilities added as tools evolve
- Deprecation of old capabilities (backward compatible)
- Capability versioning (v1 vs v2 of same capability)

---

**سوال 136: Tool Security Review**

**Review levels:**
1. **Automated (Level 1):** Static analysis, schema validation, dependency scan
2. **Manual (Level 2):** Code review for tools with network access or file access
3. **Deep (Level 3):** Full security audit for tools with destructive capabilities or external data access

**Requirements:**
- Level 1: all tools must pass (mandatory)
- Level 2: tools with network, file, or database access
- Level 3: tools with destructive ops (delete, write to external), or handling PII

**Third-party tools:**
- Must provide security documentation
- Sandbox testing: run tool in isolated environment with test inputs
- Monitor: first 1000 calls in "shadow" mode (monitor for anomalies)

**Incident response:**
- If tool compromised → immediate disable in registry
- All active tool calls: aborted
- Audit: which agents used this tool? What data was accessed?
- Post-incident: security patch → re-review → re-enable

---

### Enterprise Identity (سوال 137–140)

---

**سوال 137: Enterprise Identity Integration**

**Federation:**
- **SAML 2.0:** XML-based, enterprise standard (Azure AD, Okta)
- **OIDC:** JSON-based, modern (Google Workspace, Keycloak)
- **Both supported:** GNW supports both, auto-detect from IdP

**Identity mapping:**
- IdP user attributes → GNW user profile
- Mapping: `idp_email` → `gnw_email`, `idp_department` → `gnw_department`
- Configurable mapping per tenant

**JIT provisioning:**
- User logs in via SSO → if GNW user doesn't exist → auto-create
- Default: "member" role, default tenant
- Admin notification: new user created (for review)

**Sync:**
- Scheduled (daily): full user/group sync from IdP
- Real-time (SCIM): changes in IdP → immediate update in GNW
- If user disabled in IdP → immediate disable in GNW (revoke sessions)

---

**سوال 138: Role-Based Access Control**

**Role hierarchy:**
```
Platform Admin
  └─ Tenant Admin
       └─ Department Manager
            └─ Project Lead
                 └─ Member
                      └─ Guest
```

**Permission model:**
- Role = collection of permissions
- Permission = (resource_type, operation) e.g., ("file", "read")
- Roles inherit permissions from lower roles

**Assignment:**
- Users assigned to roles (by admin)
- Can have multiple roles (permissions = union)
- Temporary role elevation (with time limit + audit)

**Evaluation:**
- User requests operation → check: does user's role(s) include this permission?
- If yes → allow (subject to policy)
- If no → deny

---

**سوال 139: Single Sign-On**

**Flow:**
1. User accesses GNW → redirected to IdP
2. User authenticates at IdP (username/password, MFA)
3. IdP redirects back to GNW with SAML assertion / OIDC token
4. GNW validates token → creates session
5. User redirected to dashboard

**Session management:**
- Session token: JWT (stateless, no server-side session)
- TTL: 8 hours (configurable)
- Refresh: sliding window (activity extends session)
- Logout: invalidate token (add to revocation list until expiry)

**Multi-IdP:**
- Different tenants → different IdPs
- IdP discovery: based on email domain → route to correct IdP
- "Enter your email" → determine IdP → redirect

**Security:**
- MFA: enforced at IdP level
- Token signing: asymmetric (IdP signs, GNW verifies with public key)
- Replay protection: nonce in token, checked by GNW

---

**سوال 140: Directory Sync**

**Protocol:**
- SCIM 2.0 (System for Cross-domain Identity Management)
- REST API: standard endpoints for user/group CRUD

**Scope:**
- Users: all users in IdP directory → sync to GNW
- Groups: IdP groups → GNW roles (mapping configurable)
- Attributes: name, email, department, title, manager

**Conflict resolution:**
- IdP = source of truth → GNW overwritten
- If user exists only in GNW (not in IdP) → mark as "orphaned" (disable after 7 days)
- If attribute conflict → IdP wins

**Monitoring:**
- Sync success/failure: daily report
- Sync latency: target <1 hour from IdP change to GNW update
- Discrepancy alert: if GNW user count differs from IdP by >5% → investigate

---

## Phase 1 — Worker & Queue (سوال 141 تا 200)

### Run State Machine (سوال 141–150)

---

**سوال 141: State Machine Design**

**States:**
```
CREATED → VALIDATED → QUEUED → ASSIGNED → RUNNING → 
  PAUSED → RUNNING (resume) →
  COMPLETED | FAILED | CANCELLED | TIMED_OUT
```

**Transitions:**
| From | To | Trigger |
|---|---|---|
| CREATED | VALIDATED | Validation passes |
| VALIDATED | QUEUED | Enqueue |
| QUEUED | ASSIGNED | Worker claims task |
| ASSIGNED | RUNNING | Worker starts execution |
| RUNNING | PAUSED | Pause signal |
| PAUSED | RUNNING | Resume signal |
| RUNNING | COMPLETED | Task finishes successfully |
| RUNNING | FAILED | Task fails |
| RUNNING | CANCELLED | Cancel signal |
| RUNNING | TIMED_OUT | Timeout reached |
| * | CANCELLED | Cancel from any state |

**Actions:**
- On transition: persist state, emit event, update metrics, notify interested parties
- Guard conditions: e.g., QUEUED→ASSIGNED only if worker available + budget available

**Persistence:**
- State stored in durable DB (PostgreSQL)
- State transitions: atomic (DB transaction)
- Recovery: on restart, load state from DB, resume from last known state

---

**سوال 142: State Machine Events**

**Event types:**
1. **Lifecycle events:** created, queued, assigned, started, completed, failed, cancelled
2. **Control events:** pause, resume, cancel, timeout
3. **System events:** worker_died, budget_exhausted, dependency_completed
4. **Checkpoint events:** checkpoint_created, checkpoint_restored

**Validation:**
- Event schema: validate event type, required fields, source
- Transition validation: event valid for current state? (e.g., can't "complete" a "queued" task)
- Idempotency: duplicate events (same event_id) → ignored

**Ordering:**
- Events ordered by: (1) task_id, (2) sequence_number (monotonic)
- Event sourcing: state derived from event log (replayable)
- Causal: if event A caused event B → B's `caused_by = A.event_id`

**Event sourcing:**
- Event log: append-only, immutable
- Current state: derived by replaying events from beginning
- Snapshot: periodic state snapshot (for fast recovery without full replay)
- Audit: event log = complete audit trail

---

**سوال 143: State Machine Validation**

**Formal verification:**
1. Model checking: enumerate all possible state-event combinations
2. Properties to verify:
   - **Safety:** "Can't reach COMPLETED without going through RUNNING?"
   - **Liveness:** "Every QUEUED task eventually reaches ASSIGNED?"
   - **Deadlock-free:** "No state from which no progress is possible?"
3. Tools: TLA+ or SPIN model checker

**Property-based testing:**
- Generate random sequences of events
- Verify: invariants always hold (e.g., "PAUSED task doesn't consume resources")
- Edge cases: concurrent events, duplicate events, out-of-order events

**Visual verification:**
- Generate state diagram from code
- Compare with designed diagram
- Discrepancies = bugs

**Runtime validation:**
- State assertion: on every transition, verify current state matches expected
- If assertion fails → log error, enter safe state (PAUSED), alert

---

**سوال 144: State Machine Persistence**

**Storage model:**
```sql
CREATE TABLE task_states (
  task_id UUID PRIMARY KEY,
  current_state VARCHAR(32),
  previous_state VARCHAR(32),
  transition_count INT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  version INT, -- optimistic locking
  state_data JSONB -- additional state data
);
```

**Atomicity:**
- State transition = DB transaction: UPDATE state + INSERT event + UPDATE metrics
- All succeed or all fail (no partial state)
- Optimistic locking: version check prevents concurrent transitions

**Consistency:**
- Strong consistency: state always reflects latest transition
- Read-after-write: immediately after transition, state is queryable

**Performance:**
- Index on (current_state, created_at) — for queue queries
- Index on (task_id) — for individual task lookup
- Connection pooling for high throughput

---

**سوال 145: State Machine Monitoring**

**Dashboard:**
- State distribution: pie chart of tasks by state
- Transition metrics: count per transition type (per minute)
- Stuck detection: tasks in same state >expected duration → flag
- Health score: %tasks in healthy states (RUNNING, COMPLETED) vs unhealthy (FAILED, TIMED_OUT)

**Metrics:**
| Metric | Type |
|---|---|
| `tasks_by_state` | Gauge (per state) |
| `state_transitions` | Counter (per transition) |
| `time_in_state` | Histogram (per state) |
| `stuck_tasks` | Gauge |
| `state_machine_health` | Gauge (0-1) |

**Stuck detection:**
- QUEUED > 30 min → "may not have available workers"
- ASSIGNED > 5 min (not RUNNING) → "worker may be stuck"
- RUNNING > 4 hours → "may have timed out"
- PAUSED > 1 hour → "may have been forgotten"

---

**سوال 146: State Machine Error Handling**

**Invalid transition:**
- e.g., attempt to COMPLETE a QUEUED task (must go through RUNNING first)
- Response: reject event, log error, do NOT change state
- Alert: if invalid transition attempts >5/min → possible bug

**Action failure:**
- e.g., state transition requires DB write, DB is down
- Response: retry (exponential backoff, max 3)
- If retries exhausted: enter SAFE state (PAUSED), alert
- State remains consistent (transition not committed)

**State corruption:**
- Detection: state assertion fails (state doesn't match expected)
- Response: enter CRISIS mode
  1. Stop accepting new tasks
  2. Attempt state reconstruction from event log
  3. If reconstruction succeeds → resume
  4. If fails → manual intervention required

**Error recovery:**
- Automatic: retry, fallback to safe state
- Manual: admin can force state transition (with audit + risk acknowledgment)
- Post-mortem: investigate root cause of error

---

**سوال 147: State Machine Versioning**

**Version compatibility:**
- State machine v2 may have new states/transitions
- Running tasks (v1 state) must still work after v2 deployed

**Migration:**
- State mapping: v1 state → v2 state (if renamed/restructured)
- Event compatibility: v1 events still processable by v2 handler
- Graceful: v2 handler accepts v1 state, processes, may transition to v2-only states

**Graceful evolution:**
- New states: additive (don't remove old states immediately)
- New transitions: additive
- Removal: deprecate first, remove after all v1 tasks completed

**Rollback:**
- If v2 causes issues → rollback to v1
- v2-created states: mapped back to v1 equivalent
- If no v1 equivalent → map to closest v1 state (e.g., v2 "PAUSED_FOR_MIGRATION" → v1 "PAUSED")

---

**سوال 148: State Machine Testing**

**Unit tests:**
- Every transition: test valid + invalid transitions
- Every guard condition: test pass + fail
- Every action: test side effects

**Integration tests:**
- Full lifecycle: CREATED → ... → COMPLETED
- Error scenarios: worker dies mid-task → state transitions correctly
- Concurrent: multiple events on same task → no corruption

**Chaos testing:**
- Kill worker mid-transition → verify state consistency
- Network partition during transition → verify no stuck state
- DB failure during transition → verify rollback

**Regression tests:**
- Every bug fix: add test case for the bug scenario
- Version migration: v1 task → v2 handler → correct processing
- Historical bugs: replay as test cases

---

**سوال 149: Composite State**

**Hierarchical states:**
```
RUNNING (composite)
  ├── FETCHING_DATA
  ├── PROCESSING
  └── WRITING_RESULTS
```

- RUNNING is a composite state with sub-states
- Sub-states: internal transitions within RUNNING
- External view: task is "RUNNING" (detail hidden)
- Internal view: task is in "PROCESSING" sub-state

**Event propagation:**
- Events to parent state → propagate to current sub-state
- Sub-state exit → parent state still active
- Parent state exit → all sub-states exited

**Entry/exit:**
- Enter RUNNING → enter default sub-state (FETCHING_DATA)
- Exit sub-state → may transition to another sub-state or exit parent
- History state: resume last sub-state when re-entering parent

---

**سوال 150: State Machine Documentation**

**Auto-generated diagrams:**
- From code: generate Mermaid/PlantUML state diagram
- Always up-to-date (generated from actual code, not manually maintained)
- Published in documentation portal

**Transition docs:**
- For each transition: from, to, trigger, guard condition, action
- Auto-generated from code annotations

**State docs:**
- For each state: description, expected behavior, valid transitions
- Timeout: expected max duration in this state

**Change docs:**
- Version diff: "v2 added state MIGRATING, transition RUNNING→MIGRATING"
- Migration guide: "v1 tasks in RUNNING will continue, new tasks may use MIGRATING"

---

### Pause/Resume (سوال 151–156)

---

**سوال 151: Pause Mechanism**

**Triggers:**
1. User-initiated: "Pause this task"
2. System-initiated: resource pressure → pause low-priority tasks
3. Preemption: higher-priority task needs resources
4. Maintenance: worker needs to be restarted

**Signal:**
- Gateway sends `PAUSE` signal to worker
- Worker: completes current step, then pauses
- Worker: saves state (checkpoint), releases non-essential resources
- Worker: acknowledges pause

**Acknowledgment:**
- Worker must acknowledge within 30s
- If no ack → force kill (no graceful save)
- State: RUNNING → PAUSED (after ack)

**Completion:**
- After pause: task state = PAUSED, resources released (CPU, memory freed)
- Worker: available for other tasks
- Task: waiting for RESUME signal

---

**سوال 152: Pause State Saving**

**What to save:**
1. **Execution state:** current step, progress, intermediate results
2. **Memory state:** in-memory data structures (serialized)
3. **File state:** temporary files (or references to them)
4. **Network state:** active connections (endpoints + auth tokens, not connections themselves)
5. **Environment state:** environment variables, working directory

**Serialization:**
- Format: protobuf or JSON (deterministic, versioned)
- Large data: compressed + chunked
- References: large objects stored separately (object storage), state references them

**Consistency:**
- Atomic save: all or nothing (if save fails, task continues running)
- Verification: after save, verify checksum
- Version: save state machine version alongside state (for future compatibility)

**Storage:**
- Small state (<1MB): Redis (fast, for quick resume)
- Large state (>1MB): object storage (S3, compressed)
- Metadata: state location (Redis/S3), size, checksum, version

---

**سوال 153: Resume Mechanism**

**Triggers:**
1. User-initiated: "Resume this task"
2. System-initiated: resources available → resume paused tasks (priority order)
3. Scheduled: "Resume at 2 AM" (off-peak processing)
4. Dependency: paused task's dependency completed → auto-resume

**Preparation:**
1. Find available worker
2. Load checkpoint from storage
3. Verify: checksum, version compatibility
4. Restore state: deserialize, restore file references, re-establish connections
5. Worker ready

**Execution:**
- Send RESUME signal
- Worker: resumes from last checkpoint (not from start)
- State: PAUSED → RUNNING

**Failure:**
- If checkpoint corrupted → can't resume → FAILED (or restart from last good checkpoint)
- If worker can't restore state → FAILED
- If state version incompatible → migration or FAILED

---

**سوال 154: Pause/Resume Semantics**

**Checkpoint-based:**
- Pause = save checkpoint at current point
- Resume = restore from checkpoint
- Pro: simple, deterministic
- Con: may lose work between last checkpoint and pause

**Transparent:**
- Pause = freeze process (snapshot memory)
- Resume = thaw (restore memory, continue)
- Pro: no work lost
- Con: complex (needs CRIU or similar), memory snapshot may be large

**Cooperative:**
- Worker: gracefully saves state at defined save points
- Pro: clean state, application-aware
- Con: only saves at save points (not arbitrary)

**Hybrid (recommended):**
- Cooperative: regular checkpoints at save points (every 5 min)
- On pause: cooperative save at current point (if possible) + checkpoint fallback
- On resume: restore from most recent checkpoint

---

**سوال 155: Pause Resource Management**

**Release:**
- CPU: released (worker can take other tasks)
- Memory: released (state saved to storage)
- Network: connections closed
- GPU (if applicable): released
- File handles: closed

**Reclamation:**
- Worker pool: paused task's worker returns to pool
- Resources: freed for other tasks
- Metrics: resource utilization updated

**Reservation:**
- Optional: reserve resources for quick resume
- If reserved: resources held but task not executing (wasteful but fast resume)
- If not reserved: resources freed, resume needs new worker (slower)

**Restoration:**
- On resume: allocate new worker, load state, restore resources
- If original worker available → use it (warm, faster)
- If not → new worker (cold, needs state load)

---

**سوال 156: Pause/Resume Testing**

**Scenarios:**
1. Pause during data fetching → resume should continue fetching
2. Pause during processing → resume should continue from where paused
3. Pause during output writing → resume should complete output
4. Pause → worker dies → resume on new worker
5. Pause → state version upgrade → resume with migration

**State integrity:**
- After resume: verify all state variables match pre-pause
- Checksum: state checksum before pause == after resume
- Data: no data loss or duplication

**Performance:**
- Pause latency: <5s (from signal to state saved)
- Resume latency: <10s (from signal to execution resumed)
- Large state: test with 1GB state (checkpoint + restore time)

**Stress testing:**
- Rapid pause/resume cycles (100 times) → verify no state degradation
- Pause all tasks simultaneously → system handles gracefully
- Resume all tasks simultaneously → worker pool scales

---

### Cancellation (سوال 157–162)

---

**سوال 157: Cancellation Mechanism**

**Triggers:**
1. User-initiated: "Cancel this task"
2. System-initiated: kill switch, budget exhausted, policy violation
3. Dependency failure: upstream task failed
4. Timeout: task exceeded time limit

**Signal:**
- Gateway sends CANCEL signal to worker
- Worker: stop current operation, begin cleanup
- Worker: release resources, save partial results (if any)
- Worker: acknowledge cancellation

**Acknowledgment:**
- Worker must acknowledge within 30s
- If no ack → force kill (SIGKILL)
- State: * → CANCELLED

**Completion:**
- After cancellation: state = CANCELLED
- Resources: fully released
- Partial results: saved (if available) for potential reuse
- Audit: cancellation reason, timestamp, who initiated

---

**سوال 158: Graceful Cancellation**

**Flow:**
1. CANCEL signal received
2. Grace period: 30s (configurable) — worker can clean up
3. Worker: completes current atomic operation (don't leave half-done)
4. Worker: saves partial results
5. Worker: releases resources (close connections, delete temp files)
6. Worker: acknowledges cancellation complete
7. If grace period exceeded → force kill

**Cleanup guarantee:**
- Temp files: deleted (or moved to trash for 24h)
- Network connections: closed
- Database connections: closed
- Leases: revoked
- Locks: released

**Partial results:**
- If task produced useful partial output → saved with `partial: true` flag
- Agent/user can decide: use partial results or discard
- If discarded → cleanup

---

**سوال 159: Cancellation Propagation**

**Hierarchy:**
```
Parent Task
  ├── Child Task A
  ├── Child Task B
  │    └── Grandchild Task C
  └── Child Task D
```

**Propagation:**
- Parent cancelled → all children cancelled → all grandchildren cancelled
- Depth-first: cancel children first, then parent (bottom-up cleanup)
- Ordering: youngest first (reverse creation order)

**Orphans:**
- If parent dies without cancelling children → children become orphaned
- Orphan detection: periodic check (every 60s) — parent not found → cancel orphans
- Orphan handling: cancel (default) or reparent (if appropriate)

**Propagation timing:**
- Immediate: cancel signal propagates within 1s
- Graceful: each child gets grace period for cleanup
- If child doesn't acknowledge → force kill + propagate to grandchildren

---

**سوال 160: Cancellation vs Pause**

**Interactions:**

| Scenario | Behavior |
|---|---|
| Pause task → Cancel | Task in PAUSED state → cancel directly (no need to resume first) |
| Cancel during pause signal | Pause signal in-flight → cancel takes precedence (cancel, don't pause) |
| Cancel paused task → resources | Resources already released (by pause) → just mark CANCELLED |
| Pause after cancel | Invalid (CANCELLED is terminal state) → ignore |

**Priority:**
- Cancellation > Pause (cancel always wins)
- Cancellation > Resume (don't resume a cancelled task)
- Cancellation is terminal (no transition from CANCELLED to any other state)

---

**سوال 161: Cancellation Audit**

**Record:**
```
{
  "cancellation_id", "task_id", "timestamp",
  "initiated_by" (user/system), "reason",
  "cancellation_type" (graceful/forced),
  "partial_results_saved": true/false,
  "resources_released": [...],
  "children_cancelled": [...],
  "cleanup_duration_ms"
}
```

**Analysis:**
- Cancellation rate: % tasks cancelled (by reason)
- High cancellation rate → investigate: are tasks failing? User behaviour? System issues?
- Pattern: if same task type cancelled frequently → design issue

**Cost:**
- Resources consumed before cancellation: tracked and charged
- Partial results: value assessment (useful or not)
- Cleanup cost: resource cleanup time tracked

**Compliance:**
- Cancellation audit required for: compliance-critical tasks (financial, healthcare)
- "Task cancelled due to timeout — was data at risk?" → answer from audit trail

---

**سوال 162: Cancellation Safety**

**Reversal:**
- Some operations: reversible (file write → delete file)
- Some: irreversible (email sent → can't unsend)
- Cancellation: don't reverse operations, just stop future ones
- If in-flight irreversible operation → let it complete, then cancel

**Idempotency:**
- If task cancelled mid-execution → retry should be safe
- Idempotency key: same key → either complete or don't start (no partial)
- If partial execution happened → retry detects idempotency key, either continues or restarts

**Distributed:**
- Distributed task (multi-worker) → all workers must cancel
- Coordinator: sends cancel to all workers, waits for all acks
- If some workers don't ack → mark as "cancel incomplete", investigate

**Testing:**
- Cancel at various execution points → verify no side effects
- Cancel distributed task → all workers stopped
- Cancel during irreversible operation → operation completes, task cancels after

---

### Checkpoints (سوال 163–168)

---

**سوال 163: Checkpoint Strategy**

**Frequency:**
- Time-based: every 5 minutes (configurable per task type)
- Event-based: after significant milestone (e.g., "data fetched, processing begins")
- Size-based: after N MB of output produced

**Granularity:**
- Full checkpoint: entire state (every 30 min)
- Incremental: only changes since last checkpoint (every 5 min)
- Hybrid: incremental between full checkpoints

**Triggers:**
- Scheduled: timer-based
- On-demand: before maintenance window
- Pre-cancellation: save checkpoint before cancelling (for potential resume)
- Pre-migration: before migrating task to new worker

**Retention:**
- Keep last 3 checkpoints (for rollback)
- Oldest checkpoints: deleted
- Special: pre-cancellation checkpoint kept for 24h (in case user wants to resume)

---

**سوال 164: Checkpoint Storage**

**Backend:**
- Object storage (S3/OSS): large checkpoints, cost-effective
- Block storage (EBS): for fast access (hot checkpoints)
- Redis: for small checkpoints (<1MB), fast access

**Compression:**
- LZ4: fast compression/decompression (low CPU overhead)
- Ratio: ~3:1 for typical state data
- Trade-off: compression time vs storage cost

**Deduplication:**
- Content-addressable: hash of checkpoint content → if same hash, don't store duplicate
- Typical savings: 40-60% (many checkpoints share unchanged data)
- Chunk-level: deduplicate at chunk level (4MB chunks) for better ratio

**Transfer:**
- Parallel: checkpoint split into chunks, uploaded in parallel
- Resumable: if transfer interrupted, resume from incomplete chunks
- Verification: checksum per chunk + overall checksum

---

**سوال 165: Checkpoint Consistency**

**Consistent state capture:**
1. **Pause execution** (stop processing, don't accept new work)
2. **Flush buffers** (write pending I/O to stable storage)
3. **Capture state** (serialize in-memory state)
4. **Verify consistency** (checksums, cross-references)
5. **Resume execution**

**Models:**
- **Application-level:** Application knows how to checkpoint itself (cooperative)
- **System-level:** System snapshots process (CRIU) — no application awareness
- **Hybrid:** Application provides hints, system does the capture

**Verification:**
- Checksum: verify checkpoint integrity after capture
- Test restore: periodically restore from checkpoint in staging (verify it works)
- Schema: verify state schema matches expected (no corruption)

**Inconsistent checkpoint:**
- If detected: discard checkpoint, continue from previous good one
- If no previous good checkpoint: task must restart from beginning (last resort)
- Alert: inconsistent checkpoint = potential bug, investigate

---

**سوال 166: Checkpoint Recovery**

**Initiation:**
1. Task failure: worker crashed → recover from last checkpoint
2. User request: "Restart from checkpoint"
3. Migration: task moved to new worker → restore from checkpoint

**Selection:**
- Latest valid checkpoint: most recent with verified checksum
- If latest corrupted → previous checkpoint
- If all corrupted → restart from beginning (last resort)

**Execution:**
1. Find checkpoint in storage
2. Download (parallel chunks, resumable)
3. Verify: checksum, schema, version
4. Restore: deserialize, restore file references, re-establish connections
5. Resume: continue from checkpoint point

**Verification:**
- Post-restore: verify state matches expected (all variables present, no corruption)
- Smoke test: execute one step → verify output correct
- If verification fails → try previous checkpoint or FAIL

---

**سوال 167: Checkpoint Performance**

**Non-blocking:**
- Checkpointing: doesn't block execution (copy-on-write)
- Application: continues processing while checkpoint captured in background
- Trade-off: slight memory overhead (copy-on-write duplicates pages)

**Incremental:**
- Only save changed data since last checkpoint
- Change detection: page-level (memory) or field-level (application state)
- Size: incremental ~10-20% of full checkpoint

**Scheduling:**
- Low-priority: checkpoint I/O at lower priority than task execution
- Throttling: limit checkpoint bandwidth (don't saturate network)
- Off-peak: full checkpoints during low-activity periods

**Throttling:**
- If checkpointing causes >5% performance degradation → reduce frequency
- If network saturated → throttle checkpoint upload rate
- Adaptive: if task is I/O-heavy → less frequent checkpoints (I/O contention)

---

**سوال 168: Checkpoint Management**

**Metadata:**
```
{
  "checkpoint_id", "task_id", "timestamp",
  "type" (full/incremental), "size_bytes",
  "storage_location", "checksum",
  "state_machine_version", "parent_checkpoint_id" (for incremental)
}
```

**Cleanup:**
- Retention: keep last N checkpoints (default: 3)
- Expired: delete (storage freed)
- Orphaned: if task deleted → all checkpoints deleted
- Periodic: weekly sweep for orphaned checkpoints

**Migration:**
- If storage backend changed → migrate checkpoints
- Online: copy while tasks running (no downtime)
- Verification: post-migration checksum verification

**Monitoring:**
- Checkpoint count per task
- Storage usage (total, per task, per tenant)
- Checkpoint latency (capture + storage time)
- Recovery latency (restore time)
- Alert: if checkpoint storage > quota → cleanup or expand

---

### Worker Leases (سوال 169–174)

---

**سوال 169: Worker Lease Mechanism**

**Concept:**
- Worker "leases" a task for a duration
- During lease: worker is responsible for that task
- Lease expires: worker must renew or release task
- Prevents: tasks stuck on dead workers (lease expires → task requeued)

**Acquisition:**
1. Worker requests task from queue
2. Queue assigns task → creates lease (duration: 5 min)
3. Worker: lease_id, task_id, expiry
4. Worker: processes task

**Renewal:**
- Before lease expires (T-1 min): worker renews
- Renewal: extend lease by another 5 min (if task still running)
- If renewal fails (queue unreachable): worker should checkpoint + prepare for lease loss

**Expiry:**
- If lease expires (worker didn't renew): task requeued
- Worker's processing: may be wasted (if task requeued and picked up by another)
- Fencing (see Q170) prevents double-processing

---

**سوال 170: Lease Fencing**

**Fencing token:**
- Monotonically increasing number per task
- Each lease grant: fencing_token++
- Worker must present fencing_token with every operation

**Enforcement:**
- Downstream services (DB, file system): check fencing_token
- If token < current_highest → reject (stale worker)
- If token == current_highest → accept

**Gap:**
- Time between lease expiry and fencing enforcement: ~0ms (synchronous check)
- Downstream services: must participate in fencing (token validation)

**Testing:**
- Simulate: worker A's lease expires, worker B gets new lease
- Worker A: tries to write → fencing_token mismatch → rejected
- Worker B: writes → fencing_token correct → accepted
- Verify: no double-write

---

**سوال 171: Lease Duration**

**Factors:**
- Task type: short task = short lease (1 min), long task = long lease (30 min)
- Network reliability: unstable network = shorter lease (faster detection)
- Checkpoint frequency: frequent checkpoints = shorter lease OK
- Worker reliability: unreliable workers = shorter lease

**Adaptive TTL:**
- Start: default duration (5 min)
- If worker consistently renews on time → extend (10 min, 15 min)
- If worker frequently lets leases expire → shorten (2 min)
- ML: predict optimal duration based on task type + worker history

**Boundaries:**
- Min: 30 seconds (too short → excessive renewals)
- Max: 30 minutes (too long → slow failure detection)
- Recommended default: 5 minutes

---

**سوال 172: Lease Store**

**Requirements:**
- Consistency: strong (fencing tokens must be monotonically increasing)
- Availability: high (lease store down = all workers blocked)
- Performance: fast (every task operation checks lease)

**Options:**
1. **etcd/ZooKeeper:** Strong consistency, consensus-based, proven
2. **PostgreSQL:** Strong consistency, ACID, familiar
3. **Redis (with Redlock):** Fast, but weaker consistency guarantees
4. **Recommended:** etcd (purpose-built for distributed coordination)

**Operations:**
- `acquire_lease(task_id, worker_id, duration)` → lease_id, fencing_token
- `renew_lease(lease_id, duration)` → success/fail
- `release_lease(lease_id)` → success
- `check_lease(task_id)` → current_lease_info or null

**Failure:**
- If lease store unavailable:
  - Workers can't acquire new leases → no new tasks start
  - Active workers: can't renew → leases expire → tasks requeued (after store recovers)
  - Mitigation: lease store in HA mode (3-node cluster)

---

**سوال 173: Lease Monitoring**

**Metrics:**
| Metric | Type |
|---|---|
| `active_leases` | Gauge |
| `lease_acquisitions` | Counter |
| `lease_renewals` | Counter |
| `lease_expirations` | Counter |
| `lease_contention` | Gauge (competing workers per task) |
| `fencing_rejections` | Counter |
| `lease_duration` | Histogram |

**Anomalies:**
- High expiration rate: workers unreliable or lease too short
- High fencing rejections: workers operating with stale leases (bug or network issue)
- High contention: many workers competing for same task (priority issue?)

**Tracing:**
- Per-task: lease acquisition → renewals → completion/release
- Per-worker: leases held, renewals, expirations

**Alerts:**
- Expiration rate >5% of acquisitions → WARNING
- Fencing rejections >0 → WARNING (stale worker operating)
- Lease store unavailable → CRITICAL

---

**سوال 174: Lease and Task Lifecycle**

**Binding:**
- Task assigned → lease created → binding (task ↔ worker)
- During execution: lease renewed periodically
- On completion: lease released
- On failure: lease released, task may be requeued (new lease)

**Migration:**
- If task migrates: old lease released, new lease on new worker
- Fencing token: increments (new worker has higher token)
- Old worker: fencing rejects any late writes

**Failure:**
- Worker dies: lease expires → task requeued
- Lease store dies: no new leases, active leases eventually expire
- Task fails: lease released, task state = FAILED

**Preemption:**
- Higher-priority task needs worker:
  1. Worker's current lease revoked
  2. Worker: checkpoint + release task
  3. Worker: acquire higher-priority task
  4. Preempted task: requeued with same priority

---

### Retries (سوال 175–180)

---

**سوال 175: Retry Strategy**

**Retryable errors:**
- Network timeout: retry (transient)
- 5xx server error: retry (server issue)
- Rate limit (429): retry (after backoff)
- Connection refused: retry (transient)

**Non-retryable errors:**
- 4xx client error (except 429): don't retry (bad request, won't change)
- Authentication failure: don't retry (credentials wrong)
- Policy denial: don't retry (policy won't change)
- Invalid input: don't retry (input won't change)

**Policy:**
- Max retries: 3 (configurable per task type)
- Retry budget: max total retry time = 5 min
- Backoff: exponential with jitter (see Q176)

**Idempotency:**
- Retry only safe if operation is idempotent OR has idempotency key
- Non-idempotent: retry only with idempotency key (dedup)
- If no idempotency: don't retry (risk of duplicate side effects)

---

**سوال 176: Exponential Backoff**

**Formula:**
```
delay = base_delay * (2 ^ attempt) + random_jitter
```
- base_delay = 1 second
- attempt: 0, 1, 2, ...
- max_delay: 60 seconds (cap)

**Jitter types:**
1. **Full jitter:** `delay = random(0, base * 2^attempt)` — most spread
2. **Equal jitter:** `delay = base * 2^attempt / 2 + random(0, base * 2^attempt / 2)`
3. **Decorrelated jitter:** `delay = random(base, previous_delay * 3)`

**Recommendation:** Full jitter (best for thundering herd prevention).

**Example:**
- Retry 1: random(0, 2s) → e.g., 1.3s
- Retry 2: random(0, 4s) → e.g., 2.7s
- Retry 3: random(0, 8s) → e.g., 5.1s

**State:**
- Per-task: retry count, next retry time
- Per-system: total retries (for metrics)
- Circuit breaker state (see Q177)

**System load:**
- If system overloaded → backoff increases (longer delays)
- If system healthy → standard backoff
- Adaptive: monitor system health, adjust backoff multiplier

---

**سوال 177: Circuit Breaker**

**States:**
1. **CLOSED:** Normal operation, requests flow
2. **OPEN:** Failure threshold exceeded, all requests fail fast
3. **HALF_OPEN:** Testing if service recovered (limited requests)

**Threshold:**
- Failure rate >50% in 1 min (sliding window) → OPEN
- Recovery: after 30s in OPEN → HALF_OPEN
- HALF_OPEN: allow 5 requests, if all succeed → CLOSED, if any fail → OPEN

**Recovery:**
- OPEN → wait 30s → HALF_OPEN
- HALF_OPEN: 5 successful requests → CLOSED
- HALF_OPEN: 1 failure → OPEN (reset timer)

**Scope:**
- Per-service: circuit breaker for each downstream service
- Per-tenant: tenant's requests don't affect other tenants' circuits
- Per-region: if region's service down → only that region's circuit opens

**Integration with retries:**
- Retry: if circuit OPEN → don't retry (fail fast)
- Circuit CLOSED: retry normally
- Circuit HALF_OPEN: retry with caution (may be recovering)

---

**سوال 178: Retry Queue**

**Design:**
- Separate queue for failed tasks (retry queue)
- Tasks in retry queue: scheduled for future execution (delayed queue)
- Delay = backoff time (based on retry count)

**Scheduling:**
- Delayed execution: task not available for pickup until delay expires
- Priority: retry tasks have lower priority than new tasks (don't starve new work)
- Max queue size: 1000 (if exceeded → DLQ)

**Persistence:**
- Retry queue: persistent (survives restart)
- If queue lost: tasks in retry lost → logged (may need manual recovery)

**Monitoring:**
- Queue depth (by retry count)
- Time in retry queue
- Retry success rate (retried → completed)
- Retry exhaustion rate (retried → DLQ)

---

**سوال 179: Retry Exhaustion**

**Behavior:**
- After max retries (3) → task FAILED
- State: RUNNING → FAILED (exhausted)
- Notification: agent + user notified

**DLQ (Dead Letter Queue):**
- Failed tasks: moved to DLQ
- DLQ: persistent storage, retained for 7 days
- Manual retry: admin can requeue from DLQ (after fixing root cause)
- Auto-expiry: DLQ entries older than 7 days → deleted

**Notification:**
- Agent: "Task failed after 3 retries. Last error: [error message]"
- User (if applicable): "Your task failed. Reason: [reason]. You can retry from the dashboard."
- Admin: if retry exhaustion rate >5% → alert (systemic issue)

**Analysis:**
- Failure reason: categorize (network, timeout, logic error, etc.)
- Pattern: if same task type fails repeatedly → design issue
- Root cause: investigate, fix, deploy, then retry from DLQ

---

**سوال 180: Retry Testing**

**Scenarios:**
1. Transient failure → retry → success (happy path)
2. Permanent failure → retry → exhaust → DLQ
3. Rate limit → retry → backoff → success after cooldown
4. Circuit breaker open → retry fails fast → circuit recovers → retry succeeds
5. Concurrent retries (thundering herd) → jitter prevents overload

**Backoff verification:**
- Log actual delays: verify exponential growth + jitter
- Verify: delays don't exceed max_delay
- Verify: jitter distributes retries (no clustering)

**Circuit breaker testing:**
- Inject failures → verify circuit opens at threshold
- Wait → verify half-open transition
- Inject success → verify circuit closes
- Inject failure in half-open → verify re-open

**Chaos testing:**
- Kill downstream service → retries trigger → circuit opens
- Restart service → circuit recovers → retries succeed
- Network partition → retries + circuit breaker work together

---

### Idempotency Keys (سوال 181–186)

---

**سوال 181: Idempotency Key Design**

**Generation:**
- Client-generated (agent): UUID v4 or hash of request parameters
- Format: `idem_{agent_id}_{task_hash}_{nonce}`
- Must be unique per logical operation (not per request)

**Scope:**
- Per agent: same agent's retries share key
- Per task: different tasks = different keys
- Per operation: same operation retried = same key

**Format:**
- UUID v4: `550e8400-e29b-41d4-a716-446655440000`
- Hash-based: SHA-256(agent_id + tool + params) → first 32 chars
- Structured: `idem:{agent_id}:{task_id}:{step_id}`

**Validation:**
- Must be non-empty
- Must be valid format (UUID or structured)
- Must not contain sensitive data (PII, credentials)
- Max length: 128 chars

---

**سوال 182: Idempotency Key Lifecycle**

**Creation:**
- Key created when first request arrives
- Store entry: key → {status: in_progress, result: null, timestamp, expiry}

**States:**
- `IN_PROGRESS`: Request being processed
- `COMPLETED`: Result stored, ready to return for duplicates
- `FAILED`: Request failed, can be retried (key available for retry)
- `EXPIRED`: TTL exceeded, key can be reused

**Cleanup:**
- TTL: 24 hours (configurable)
- Periodic sweep: every hour, delete expired keys
- Storage: if key store > threshold → accelerate cleanup

**Storage bloat prevention:**
- Max key store size: configurable per tenant
- If exceeded: accelerate cleanup (reduce TTL)
- Alert: if store size growing → possible leak (keys not being cleaned)

---

**سوال 183: Idempotency and Concurrency**

**Concurrent requests with same key:**
1. Request A arrives → key not in store → create entry (IN_PROGRESS) → acquire lock
2. Request B arrives (before A completes) → key IN_PROGRESS → wait for lock
3. Request A completes → store result (COMPLETED) → release lock
4. Request B → gets cached result (doesn't re-execute)

**Locking:**
- Distributed lock (Redis SETNX with TTL)
- Lock key: `idem_lock:{idempotency_key}`
- Lock TTL: 5 min (if worker dies, lock auto-releases)
- Lock holder: request_id (to identify who holds lock)

**Timeout:**
- If lock wait >30s → return 409 Conflict ("operation in progress")
- Client should retry with same key (will get cached result if completed)

**Race condition:**
- Prevention: atomic check-and-create (Redis SETNX or DB unique constraint)
- If race: only one request creates entry, others get "already exists" → wait or return cached

---

**سوال 184: Idempotency Key in Distributed Systems**

**Propagation:**
- Idempotency key in request header: `Idempotency-Key: {key}`
- Propagated through all service calls (in trace context)
- Downstream services: can also use same key for their own idempotency

**Cross-service:**
- Service A → Service B: same key passed
- Service B: checks its own idempotency store
- If key exists in B's store → B returns cached result (doesn't re-execute)

**Partial failure:**
- Service A succeeds, Service B fails:
  - Service A's result: stored (completed)
  - Service B: failed, can retry
  - On retry: Service A (cached, not re-executed) → Service B (retry)
- Result: operation completes correctly, no duplicate work in A

**Cross-region:**
- Each region: own idempotency store
- Cross-region requests: key includes region prefix
- If region down: failover to other region (new key for new region)

---

**سوال 185: Idempotency Key and Retry**

**Same key:**
- Client retries with same idempotency key
- Server: finds key → returns cached result (if completed)
- Result: client gets same response as original (no duplicate execution)

**New key:**
- If client generates new key for retry (shouldn't, but possible):
  - Server: doesn't find key → executes again → duplicate side effects
  - This is a client bug (should reuse same key)

**Selection:**
- Client must: store idempotency key with request context
- On retry: use stored key (not generate new one)
- If key lost (client restart): can't retry safely → must accept potential duplicate

**Exhaustion:**
- If retries exhausted:
  - Key entry: status = FAILED
  - Can retry again later (key still available, status FAILED allows retry)
  - If key expired: new key needed → risk of duplicate (mitigate with application-level dedup)

---

**سوال 186: Idempotency Key Observability**

**Metrics:**
| Metric | Type |
|---|---|
| `idempotency_keys_active` | Gauge |
| `duplicate_requests_total` | Counter (detected duplicates) |
| `idempotency_cache_hits` | Counter |
| `idempotency_cache_misses` | Counter |
| `concurrent_key_collisions` | Counter (same key concurrent) |
| `key_store_size` | Gauge |

**Duplicate analysis:**
- Duplicate rate: duplicates / total requests
- High duplicate rate → client retrying too aggressively or network issues
- Per-agent: which agents send most duplicates?

**Debugging:**
- Key trace: log key lifecycle (created → in_progress → completed)
- If duplicate detected: log original request_id + duplicate request_id
- If key collision (different operations, same key): log both operations for investigation

**Alerts:**
- Duplicate rate >10% → WARNING (possible client bug)
- Key store size > quota → WARNING (cleanup needed)
- Concurrent collisions >5% → WARNING (clients not waiting for responses)

---

### Crash Recovery (سوال 187–192)

---

**سوال 187: Crash Recovery Architecture**

**Detection:**
1. **Heartbeat loss:** Worker doesn't report for 3 intervals → crashed
2. **Task timeout:** Task not progressing → worker may be stuck (not crashed, but similar handling)
3. **Health check fail:** Health check returns error → crashed
4. **Process monitor:** OS-level process monitoring (systemd, k8s liveness)

**Classification:**
- **Worker crash:** Process died → restart worker, recover tasks
- **Worker stuck:** Process alive but not progressing → kill + restart
- **Worker degraded:** Process alive, responding, but errors → quarantine
- **Network partition:** Worker alive but unreachable → treat as crashed (can't verify)

**Actions:**
1. Mark worker as UNHEALTHY
2. Requeue worker's active tasks (leases expired)
3. Restart worker (if crash) or kill+restart (if stuck)
4. Tasks: recover from last checkpoint (if available) or restart
5. Notify: tasks affected, reason, recovery status

**Orchestration:**
- Recovery coordinator: manages recovery for multiple workers
- Parallel: multiple workers recovered simultaneously
- Priority: high-priority tasks recovered first

---

**سوال 188: Crash-Consistent State**

**WAL (Write-Ahead Log):**
- Before any state change: write to WAL
- WAL: append-only, durable (fsync before write)
- On crash: replay WAL to reconstruct state
- Checkpoint: periodic WAL truncation (save state, delete WAL up to checkpoint)

**Atomic operations:**
- State changes: atomic (DB transaction or CAS)
- File writes: atomic (write to temp, rename) or use WAL
- No partial states: either old state or new state (never in-between)

**Corruption detection:**
- Checksum: per-state, per-WAL entry
- If checksum mismatch → corruption detected
- Recovery: discard corrupted data, use last valid checkpoint

**Stateless design:**
- If workers are stateless (all state in external store) → crash recovery = just restart
- No in-memory state to lose
- Trade-off: external store access latency (slower than in-memory)

---

**سوال 189: Crash Recovery Time**

**RTO (Recovery Time Objective):**
- Target: <5 minutes (from crash detection to task resumed)
- Breakdown: detection (30s) + requeue (10s) + checkpoint restore (2min) + resume (30s)

**Bottlenecks:**
1. **Detection time:** heartbeat interval (30s default)
2. **Checkpoint download:** large checkpoints (GBs) take time
3. **Worker startup:** cold start (~3s for container)
4. **State restoration:** deserialization, connection setup

**Fast recovery:**
- Reduce detection: shorter heartbeat (10s) — more overhead but faster detection
- Pre-fetch checkpoints: keep recent checkpoints in fast storage
- Warm workers: pre-started workers ready to take over
- Streaming restore: start processing as checkpoint loads (don't wait for full load)

**Monitoring:**
- Recovery time: per incident (detection → resume)
- Trend: is recovery time increasing? (larger checkpoints?)
- Alert: if recovery >10 min → CRITICAL

---

**سوال 190: Crash Recovery Testing**

**Scenarios:**
1. Kill worker process (SIGKILL) → verify tasks recovered
2. Network partition worker → verify detected + recovered
3. Worker OOM killed → verify tasks recovered
4. Disk full on worker → verify graceful handling
5. Power loss (VM) → verify cold recovery

**Chaos engineering:**
- Random worker kills (during business hours, controlled)
- Inject: network latency, disk I/O errors, memory pressure
- Measure: detection time, recovery time, data loss (if any)

**Verification:**
- State: after recovery, verify state matches pre-crash
- Data: no data loss or duplication
- Idempotency: if task re-executed, verify no duplicate side effects
- Checkpoint: verify checkpoint was valid and restored correctly

**Game days:**
- Quarterly: simulated disaster (multiple workers crash simultaneously)
- Team exercise: practice recovery procedures
- Post-mortem: what worked, what didn't, action items

---

**سوال 191: Graceful Degradation**

**Modes:**
1. **Full operation:** All systems healthy, full functionality
2. **Degraded operation:** Some systems degraded, reduced functionality
3. **Minimal operation:** Critical systems only, basic functionality
4. **Emergency operation:** Kill switch active, read-only or halted

**Triggers:**
- Component failure: browser workers down → disable web research, other features still work
- Resource pressure: memory low → reduce parallelism, shed load
- Network issues: external API down → use cache, skip real-time data
- Budget exhaustion: no budget left → read-only mode (no tool calls)

**Policy:**
- Per-component: define degradation behavior (what features shed, in what order)
- Per-tenant: gold tenants get priority (less degradation), bronze degraded first
- Automatic: health monitor triggers degradation based on thresholds

**Recovery:**
- Component recovers → gradually restore features
- Canary: restore 10% → verify → restore 50% → verify → 100%
- If recovery causes new issues → re-degrade

---

**سوال 192: Post-Crash Analysis**

**Data collection:**
1. **Worker logs:** last N log lines before crash
2. **System metrics:** CPU, memory, network, disk at time of crash
3. **Task state:** what task was running, what step, what input
4. **Checkpoint:** last checkpoint (for comparison)
5. **Core dump:** if available (for segfault analysis)
6. **Environment:** worker version, container image, OS, kernel

**Root cause:**
- Analyze: logs, metrics, core dump
- Pattern: is this a known issue? Has it happened before?
- Hypothesis: test (reproduce in staging)
- Root cause: identify and document

**Impact:**
- Tasks affected: count, duration of interruption
- Data: any loss or corruption?
- Users: which tenants/users affected
- Cost: resources wasted, recovery cost

**Prevention:**
- Fix: deploy patch
- Monitor: add alert for similar patterns
- Test: add regression test
- Document: update runbook for future similar incidents

---

### Queue & Autoscaling (سوال 193–200)

---

**سوال 193: Queue Architecture**

**Model:**
- Priority queue: multiple sub-queues by priority (P0, P1, P2, P3)
- Within priority: FIFO (first-in-first-out)
- Delayed queue: for retry tasks (not available until d
<truncated 8263 bytes>

NOTE: The output was truncated because it was too long. Use a more targeted query or a smaller range to get the information you need.