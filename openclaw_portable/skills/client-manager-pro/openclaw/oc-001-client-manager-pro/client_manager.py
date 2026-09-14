"""
Client-Manager-Pro (OC-001) — Core Implementation
====================================================
Automated client communication across Slack, Email, WhatsApp.
"""

import asyncio
import copy
import json
import math
import os
import re
import smtplib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────────────────────

class Channel(Enum):
    EMAIL = "email"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    SMS = "sms"


class MessageStatus(Enum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    SCHEDULED = "scheduled"
    DRY_RUN = "dry_run"
    REJECTED = "rejected"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    REPLIED = "replied"
    FAILED = "failed"
    BOUNCED = "bounced"


class Priority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class Client:
    id: str
    name: str
    email: str
    phone: str = ""
    slack_id: str = ""
    company: str = ""
    timezone: str = "UTC"
    tags: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_contacted: Optional[str] = None
    total_messages: int = 0
    response_rate: float = 0.0


@dataclass
class Message:
    id: str
    client_id: str
    channel: str
    subject: str
    body: str
    status: str = "draft"
    priority: int = 2
    scheduled_at: Optional[str] = None
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    read_at: Optional[str] = None
    replied_at: Optional[str] = None
    template_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Template:
    id: str
    name: str
    subject: str
    body: str
    channel: str
    variables: List[str] = field(default_factory=list)
    category: str = "general"
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    usage_count: int = 0
    conversion_rate: float = 0.0


@dataclass
class FollowUpSequence:
    id: str
    name: str
    client_id: str
    steps: List[Dict]  # [{delay_hours, template_id, channel}]
    current_step: int = 0
    status: str = "active"  # active, paused, completed, cancelled
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    next_run: Optional[str] = None
    pending_approval_id: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# TEMPLATE ENGINE
# ──────────────────────────────────────────────────────────────

class TemplateEngine:
    """Jinja2-based template engine with variable validation."""
    
    def __init__(self):
        self.templates: Dict[str, Template] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """Load built-in templates."""
        defaults = [
            Template(
                id="welcome",
                name="Welcome Email",
                subject="Welcome to {{company_name}} — Let's Get Started",
                body="""Hi {{client_name}},

Thank you for choosing {{company_name}}! I'm {{sender_name}}, and I'll be your dedicated point of contact.

Here's what happens next:
1. We'll schedule a kickoff call within {{kickoff_days}} days
2. You'll receive access to our client portal
3. I'll send you a detailed onboarding checklist

In the meantime, feel free to reply to this email with any questions.

Best regards,
{{sender_name}}
{{sender_title}}
{{company_name}}""",
                channel="email",
                variables=["client_name", "company_name", "sender_name", "sender_title", "kickoff_days"],
                category="onboarding"
            ),
            Template(
                id="follow_up_1",
                name="First Follow-up",
                subject="Following up — {{original_subject}}",
                body="""Hi {{client_name}},

I wanted to follow up on my previous message about {{topic}}. 

I know you're busy, so I'll keep this short:
- {{key_point_1}}
- {{key_point_2}}

Would you have 15 minutes this week for a quick call?

Best,
{{sender_name}}""",
                channel="email",
                variables=["client_name", "original_subject", "topic", "key_point_1", "key_point_2", "sender_name"],
                category="follow_up"
            ),
            Template(
                id="meeting_reminder",
                name="Meeting Reminder",
                subject="Reminder: {{meeting_title}} — {{meeting_time}}",
                body="""Hi {{client_name}},

This is a friendly reminder about our meeting:

**{{meeting_title}}**
📅 {{meeting_date}}
⏰ {{meeting_time}} ({{timezone}})
🔗 {{meeting_link}}

Agenda:
{{agenda_items}}

Please let me know if you need to reschedule.

Best,
{{sender_name}}""",
                channel="email",
                variables=["client_name", "meeting_title", "meeting_date", "meeting_time", "timezone", "meeting_link", "agenda_items", "sender_name"],
                category="scheduling"
            ),
            Template(
                id="proposal_follow_up",
                name="Proposal Follow-up",
                subject="Your proposal is ready — {{proposal_name}}",
                body="""Hi {{client_name}},

I've prepared the proposal for {{proposal_name}}. Here's a summary:

**Investment:** {{investment_amount}}
**Timeline:** {{timeline}}
**Deliverables:** {{deliverables}}

I've attached the full proposal. Would you like to schedule a call to discuss?

Best,
{{sender_name}}""",
                channel="email",
                variables=["client_name", "proposal_name", "investment_amount", "timeline", "deliverables", "sender_name"],
                category="sales"
            ),
        ]
        
        for template in defaults:
            self.templates[template.id] = template
    
    def render(self, template_id: str, variables: Dict[str, Any]) -> Tuple[str, str]:
        """Render a template with variables. Returns (subject, body)."""
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        # Check required variables
        missing = [v for v in template.variables if v not in variables]
        if missing:
            raise ValueError(f"Missing variables: {missing}")
        
        # Simple variable substitution
        subject = template.subject
        body = template.body
        
        for key, value in variables.items():
            placeholder = "{{" + key + "}}"
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))
        
        # Update usage
        template.usage_count += 1
        
        return subject, body
    
    def extract_variables(self, template_id: str) -> List[str]:
        """Extract variable names from template."""
        template = self.templates.get(template_id)
        if not template:
            return []
        
        text = template.subject + template.body
        return re.findall(r'\{\{(\w+)\}\}', text)
    
    def validate_variables(self, template_id: str, variables: Dict) -> List[str]:
        """Validate that all required variables are present."""
        required = self.extract_variables(template_id)
        return [v for v in required if v not in variables]


# ──────────────────────────────────────────────────────────────
# CHANNEL HANDLERS
# ──────────────────────────────────────────────────────────────

def _validate_timeout(timeout: float) -> float:
    try:
        value = float(timeout)
    except (TypeError, ValueError):
        raise ValueError("timeout must be a finite positive number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout must be a finite positive number")
    return value


class EmailChannel:
    """SMTP email channel with a bounded network timeout."""

    def __init__(self, smtp_host: str = None, smtp_port: int = 587,
                 username: str = None, password: str = None,
                 from_addr: str = None, timeout: float = 10.0,
                 load_environment: bool = True):
        self.timeout = _validate_timeout(timeout)
        if load_environment:
            self.smtp_host = smtp_host or os.environ.get("SMTP_HOST", "smtp.gmail.com")
            self.smtp_port = smtp_port or int(os.environ.get("SMTP_PORT", "587"))
            self.username = username or os.environ.get("SMTP_USERNAME")
            self.password = password or os.environ.get("SMTP_PASSWORD")
            self.from_addr = from_addr or os.environ.get("SMTP_FROM", self.username)
        else:
            self.smtp_host = smtp_host
            self.smtp_port = smtp_port
            self.username = username
            self.password = password
            self.from_addr = from_addr

    async def send(self, to_addr: str, subject: str, body: str,
                   html_body: str = None) -> Dict:
        """Send email; callers must enforce approval before invoking this method."""
        try:
            if not self.smtp_host or not self.from_addr:
                return {"success": False, "error": "SMTP provider is not configured", "channel": "email"}
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_addr
            msg["To"] = to_addr
            msg.attach(MIMEText(body, "plain"))
            if html_body:
                msg.attach(MIMEText(html_body, "html"))
            loop = asyncio.get_running_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, self._send_sync, msg), self.timeout
            )
            return {"success": True, "channel": "email", "to": to_addr}
        except Exception as e:
            return {"success": False, "error": str(e), "channel": "email"}

    def _send_sync(self, msg: MIMEMultipart):
        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)


class SlackChannel:
    """Slack Web API channel with a bounded request timeout."""

    def __init__(self, bot_token: str = None, timeout: float = 10.0,
                 load_environment: bool = True):
        self.timeout = _validate_timeout(timeout)
        self.bot_token = (bot_token or os.environ.get("SLACK_BOT_TOKEN")) if load_environment else bot_token
        self.base_url = "https://slack.com/api"

    async def send(self, channel_id: str, text: str,
                   blocks: List[Dict] = None) -> Dict:
        try:
            if not self.bot_token:
                return {"success": False, "error": "Slack provider is not configured", "channel": "slack"}
            import aiohttp
            payload = {"channel": channel_id, "text": text}
            if blocks:
                payload["blocks"] = blocks
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.base_url}/chat.postMessage",
                    headers={"Authorization": f"Bearer {self.bot_token}"},
                    json=payload,
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        return {"success": True, "channel": "slack", "ts": data.get("ts")}
                    return {"success": False, "error": data.get("error"), "channel": "slack"}
        except Exception as e:
            return {"success": False, "error": str(e), "channel": "slack"}


class WhatsAppChannel:
    """Twilio WhatsApp channel with a bounded request timeout."""

    def __init__(self, account_sid: str = None, auth_token: str = None,
                 from_number: str = None, timeout: float = 10.0,
                 load_environment: bool = True):
        self.timeout = _validate_timeout(timeout)
        if load_environment:
            self.account_sid = account_sid or os.environ.get("TWILIO_ACCOUNT_SID")
            self.auth_token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN")
            self.from_number = from_number or os.environ.get("TWILIO_WHATSAPP_NUMBER")
        else:
            self.account_sid = account_sid
            self.auth_token = auth_token
            self.from_number = from_number

    async def send(self, to_number: str, body: str) -> Dict:
        try:
            if not all((self.account_sid, self.auth_token, self.from_number)):
                return {"success": False, "error": "WhatsApp provider is not configured", "channel": "whatsapp"}
            import aiohttp
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            payload = {"From": f"whatsapp:{self.from_number}", "To": f"whatsapp:{to_number}", "Body": body}
            auth = aiohttp.BasicAuth(self.account_sid, self.auth_token)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, data=payload, auth=auth) as resp:
                    data = await resp.json()
                    if resp.status == 201:
                        return {"success": True, "channel": "whatsapp", "sid": data.get("sid")}
                    return {"success": False, "error": data.get("message"), "channel": "whatsapp"}
        except Exception as e:
            return {"success": False, "error": str(e), "channel": "whatsapp"}


# ──────────────────────────────────────────────────────────────
# SAFETY
# ──────────────────────────────────────────────────────────────

class RateLimiter:
    """Per-channel rate limiting."""
    
    def __init__(self, limits: Dict[str, int] = None):
        self.limits = limits or {
            "email": 50,      # per hour
            "slack": 100,
            "whatsapp": 30,
        }
        self.counters: Dict[str, List[datetime]] = {ch: [] for ch in self.limits}
    
    def check(self, channel: str) -> Tuple[bool, str]:
        """Check if channel is under rate limit."""
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        
        # Clean old entries
        self.counters[channel] = [t for t in self.counters[channel] if t > hour_ago]
        
        current = len(self.counters[channel])
        limit = self.limits.get(channel, 50)
        
        if current >= limit:
            return False, f"Rate limit exceeded for {channel}: {current}/{limit} per hour"
        
        return True, f"{channel}: {current}/{limit}"
    
    def record(self, channel: str):
        """Record a message send."""
        self.counters[channel].append(datetime.now(timezone.utc))


class CircuitBreaker:
    """Circuit breaker for channel failures."""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures: Dict[str, int] = {}
        self.last_failure: Dict[str, datetime] = {}
        self.state: Dict[str, str] = {}  # closed, open, half-open
    
    def check(self, channel: str) -> Tuple[bool, str]:
        """Check if channel circuit is closed."""
        state = self.state.get(channel, "closed")
        
        if state == "open":
            # Check if we should try half-open
            last = self.last_failure.get(channel)
            if last and (datetime.now(timezone.utc) - last).total_seconds() > self.reset_timeout:
                self.state[channel] = "half-open"
                return True, f"Circuit half-open for {channel}, testing..."
            return False, f"Circuit open for {channel}, too many failures"
        
        return True, f"Circuit closed for {channel}"
    
    def record_success(self, channel: str):
        """Record successful send."""
        self.failures[channel] = 0
        self.state[channel] = "closed"
    
    def record_failure(self, channel: str):
        """Record failed send."""
        self.failures[channel] = self.failures.get(channel, 0) + 1
        self.last_failure[channel] = datetime.now(timezone.utc)
        
        if self.failures[channel] >= self.failure_threshold:
            self.state[channel] = "open"


class ApprovalGate:
    """Fail-closed approval workflow with authorized, immutable decisions."""

    TERMINAL = frozenset({"approved", "rejected"})

    def __init__(self, authorized_approvers: Optional[List[str]] = None,
                 approvers: Optional[List[str]] = None):
        # Keep the historical ``approvers`` attribute while making an empty
        # allow-list fail closed.
        self.approvers: List[str] = list(authorized_approvers or approvers or [])
        self._pending: Dict[str, Dict] = {}

    @property
    def pending(self) -> Dict[str, Dict]:
        """Return a snapshot; transition records cannot be mutated externally."""
        return copy.deepcopy(self._pending)

    def add_approver(self, approver: str) -> None:
        if not isinstance(approver, str) or not approver.strip():
            raise ValueError("approver must be a non-empty identifier")
        if approver not in self.approvers:
            self.approvers.append(approver)

    def request_approval(self, action: str, details: Dict) -> str:
        approval_id = str(uuid.uuid4())[:8]
        self._pending[approval_id] = {
            "action": action,
            "details": copy.deepcopy(details),
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }
        return approval_id

    def approve(self, approval_id: str, approver: str) -> bool:
        record = self._pending.get(approval_id)
        if not record or record.get("status") != "pending" or approver not in self.approvers:
            return False
        record["status"] = "approved"
        record["approved_by"] = approver
        record["approved_at"] = datetime.now(timezone.utc).isoformat()
        return True

    def reject(self, approval_id: str, approver: str, reason: str = "") -> bool:
        record = self._pending.get(approval_id)
        if not record or record.get("status") != "pending" or approver not in self.approvers:
            return False
        record["status"] = "rejected"
        record["rejected_by"] = approver
        record["rejected_at"] = datetime.now(timezone.utc).isoformat()
        record["rejection_reason"] = reason
        return True

    def is_approved(self, approval_id: str) -> bool:
        return self._pending.get(approval_id, {}).get("status") == "approved"

    def get(self, approval_id: str) -> Optional[Dict]:
        record = self._pending.get(approval_id)
        return copy.deepcopy(record) if record else None


# ──────────────────────────────────────────────────────────────
# MAIN CLIENT MANAGER
# ──────────────────────────────────────────────────────────────

class ClientManagerPro:
    """Client-Manager-Pro — main implementation."""
    
    def __init__(self, storage_path: str = "~/.openclaw/client_manager",
                 dry_run: bool = True, provider_timeout: float = 10.0,
                 authorized_approvers: Optional[List[str]] = None):
        self.storage_path = Path(storage_path).expanduser()
        self.dry_run = bool(dry_run)
        self.provider_timeout = _validate_timeout(provider_timeout)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Data stores
        self.clients: Dict[str, Client] = {}
        self.messages: Dict[str, Message] = {}
        self.sequences: Dict[str, FollowUpSequence] = {}
        
        # Components
        self.templates = TemplateEngine()
        self.rate_limiter = RateLimiter()
        self.circuit_breaker = CircuitBreaker()
        self.approval = ApprovalGate(authorized_approvers=authorized_approvers)
        
        # Provider construction is offline-safe: credentials are not read unless
        # a caller explicitly constructs a provider with load_environment=True.
        self.email = EmailChannel(timeout=self.provider_timeout, load_environment=False)
        self.slack = SlackChannel(timeout=self.provider_timeout, load_environment=False)
        self.whatsapp = WhatsAppChannel(timeout=self.provider_timeout, load_environment=False)
        
        # Scheduler
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Audit
        self.audit_log: List[Dict] = []
        
        self._load_data()
    
    def _load_data(self):
        """Load data from disk."""
        # Load clients
        clients_file = self.storage_path / "clients.json"
        if clients_file.exists():
            with open(clients_file) as f:
                data = json.load(f)
                for c in data:
                    self.clients[c["id"]] = Client(**c)
        
        # Load messages
        messages_file = self.storage_path / "messages.json"
        if messages_file.exists():
            with open(messages_file) as f:
                data = json.load(f)
                for m in data:
                    self.messages[m["id"]] = Message(**m)
    
    def _save_data(self):
        """Save data to disk."""
        with open(self.storage_path / "clients.json", "w") as f:
            json.dump([asdict(c) for c in self.clients.values()], f, indent=2, default=str)
        
        with open(self.storage_path / "messages.json", "w") as f:
            json.dump([asdict(m) for m in self.messages.values()], f, indent=2, default=str)
    
    def _audit(self, action: str, actor: str, target: str, result: str, metadata: Dict = None):
        """Log audit entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "actor": actor,
            "target": target,
            "result": result,
            "metadata": metadata or {},
            "audit_id": str(uuid.uuid4())[:8]
        }
        self.audit_log.append(entry)
        
        # Save audit log
        audit_file = self.storage_path / "audit.jsonl"
        with open(audit_file, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    
    # ── Client Management ──
    
    def add_client(self, name: str, email: str, **kwargs) -> Client:
        """Add a new client."""
        client_id = str(uuid.uuid4())[:8]
        client = Client(
            id=client_id,
            name=name,
            email=email,
            **kwargs
        )
        self.clients[client_id] = client
        self._save_data()
        
        self._audit("client_added", "user", client_id, "success", {"name": name, "email": email})
        return client
    
    def get_client(self, client_id: str) -> Optional[Client]:
        """Get client by ID."""
        return self.clients.get(client_id)
    
    def find_clients(self, query: str) -> List[Client]:
        """Search clients by name, email, or company."""
        query_lower = query.lower()
        return [
            c for c in self.clients.values()
            if query_lower in c.name.lower()
            or query_lower in c.email.lower()
            or query_lower in c.company.lower()
            or any(query_lower in t.lower() for t in c.tags)
        ]
    
    # ── Message Sending ──
    
    @staticmethod
    def _parse_schedule(schedule_at: str) -> datetime:
        if not isinstance(schedule_at, str) or not schedule_at.strip():
            raise ValueError("schedule_at must be an ISO-8601 timestamp")
        try:
            value = datetime.fromisoformat(schedule_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("schedule_at must be a valid ISO-8601 timestamp") from exc
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("schedule_at must include a timezone")
        now = datetime.now(timezone.utc)
        value = value.astimezone(timezone.utc)
        if value <= now:
            raise ValueError("schedule_at must be in the future")
        if value > now + timedelta(days=365):
            raise ValueError("schedule_at is beyond the one-year safety bound")
        return value

    def _message_for_approval(self, message: Message) -> str:
        approval_id = self.approval.request_approval("external_send", {
            "message_id": message.id,
            "client_id": message.client_id,
            "channel": message.channel,
            "subject": message.subject,
            "body": message.body,
            "scheduled_at": message.scheduled_at,
        })
        message.metadata["approval_id"] = approval_id
        message.status = MessageStatus.AWAITING_APPROVAL.value
        return approval_id

    async def send_message(
        self,
        client_id: str,
        template_id: str,
        variables: Dict[str, Any],
        channel: str = None,
        priority: Priority = Priority.NORMAL,
        schedule_at: str = None,
    ) -> Dict:
        """Create a message and always stop at a fail-closed approval gate."""
        client = self.get_client(client_id)
        if not client:
            return {"success": False, "error": f"Client {client_id} not found"}
        channel = channel or self._get_default_channel(client)
        if channel not in {"email", "slack", "whatsapp"}:
            return {"success": False, "error": f"Unknown channel: {channel}"}
        if schedule_at is not None:
            try:
                schedule_at = self._parse_schedule(schedule_at).isoformat()
            except ValueError as exc:
                return {"success": False, "error": str(exc)}
        ok, msg = self.rate_limiter.check(channel)
        if not ok:
            self._audit("send_blocked", "user", client_id, "rate_limit", {"channel": channel})
            return {"success": False, "error": msg, "rate_limited": True}
        ok, msg = self.circuit_breaker.check(channel)
        if not ok:
            self._audit("send_blocked", "user", client_id, "circuit_open", {"channel": channel})
            return {"success": False, "error": msg, "circuit_open": True}
        try:
            subject, body = self.templates.render(template_id, variables)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        try:
            priority_value = priority.value if isinstance(priority, Priority) else int(priority)
        except (TypeError, ValueError):
            return {"success": False, "error": "invalid priority"}
        if priority_value not in {p.value for p in Priority}:
            return {"success": False, "error": "invalid priority"}
        message = Message(
            id=str(uuid.uuid4())[:8], client_id=client_id, channel=channel,
            subject=subject, body=body, priority=priority_value,
            scheduled_at=schedule_at, template_id=template_id,
            status=MessageStatus.DRAFT.value,
        )
        self.messages[message.id] = message
        approval_id = self._message_for_approval(message)
        self._audit("approval_requested", "user", message.id, "pending", {
            "approval_id": approval_id, "client": client_id, "channel": channel,
        })
        self._save_data()
        return {
            "success": False, "approval_required": True, "approval_id": approval_id,
            "message_id": message.id, "status": message.status, "dry_run": self.dry_run,
        }

    async def approve_and_send(self, approval_id: str, approver: str) -> Dict:
        """Approve exactly once, then dispatch only that approved message."""
        if not self.approval.approve(approval_id, approver):
            return {"success": False, "error": "approval is invalid, terminal, or approver is unauthorized"}
        return await self.dispatch_approved(approval_id)

    async def dispatch_approved(self, approval_id: str) -> Dict:
        record = self.approval.get(approval_id)
        if not record or record.get("status") != "approved":
            return {"success": False, "error": "approved approval record required"}
        message_id = record.get("details", {}).get("message_id")
        message = self.messages.get(message_id)
        if not message:
            return {"success": False, "error": "message for approval not found"}
        if message.status in {"sent", "failed", "dry_run", "rejected"}:
            return {"success": False, "error": "message is already terminal", "message_id": message.id}
        if message.scheduled_at:
            due = datetime.fromisoformat(message.scheduled_at)
            if due > datetime.now(timezone.utc):
                message.status = MessageStatus.SCHEDULED.value
                self._audit("message_scheduled", record.get("approved_by", "approver"), message.id, "success", {
                    "scheduled_at": message.scheduled_at, "approval_id": approval_id,
                })
                self._save_data()
                return {"success": True, "message_id": message.id, "status": message.status}
        client = self.get_client(message.client_id)
        if not client:
            message.status = MessageStatus.FAILED.value
            self._save_data()
            return {"success": False, "error": "client for approved message not found", "message_id": message.id}
        return await self._send_now(message, client)

    async def _send_now(self, message: Message, client: Client) -> Dict:
        """Send only an approved message; default mode performs no provider call."""
        approval_id = message.metadata.get("approval_id")
        if not approval_id or not self.approval.is_approved(approval_id):
            return {"success": False, "error": "external send requires an authorized approval", "message_id": message.id}
        if self.dry_run:
            message.status = MessageStatus.DRY_RUN.value
            self._audit("message_dry_run", "system", message.id, "success", {"channel": message.channel})
            self._save_data()
            return {"success": True, "dry_run": True, "channel": message.channel, "message_id": message.id}
        channel = message.channel
        try:
            if channel == "email":
                result = await self.email.send(client.email, message.subject, message.body)
            elif channel == "slack":
                result = await self.slack.send(client.slack_id, message.body)
            elif channel == "whatsapp":
                result = await self.whatsapp.send(client.phone, message.body)
            else:
                result = {"success": False, "error": f"Unknown channel: {channel}"}
            if result.get("success"):
                message.status = MessageStatus.SENT.value
                message.sent_at = datetime.now(timezone.utc).isoformat()
                self.rate_limiter.record(channel)
                self.circuit_breaker.record_success(channel)
                client.last_contacted = message.sent_at
                client.total_messages += 1
                self._audit("message_sent", "system", message.id, "success", {"client": client.id, "channel": channel})
            else:
                message.status = MessageStatus.FAILED.value
                self.circuit_breaker.record_failure(channel)
                self._audit("message_failed", "system", message.id, "failure", {
                    "client": client.id, "channel": channel, "error": result.get("error"),
                })
            self._save_data()
            return {**result, "message_id": message.id}
        except Exception as exc:
            message.status = MessageStatus.FAILED.value
            self.circuit_breaker.record_failure(channel)
            self._audit("message_error", "system", message.id, "failure", {"client": client.id, "error": str(exc)})
            self._save_data()
            return {"success": False, "error": str(exc), "message_id": message.id}

    def _get_default_channel(self, client: Client) -> str:
        """Get default channel for client."""
        if client.slack_id:
            return "slack"
        elif client.phone:
            return "whatsapp"
        else:
            return "email"
    
    # ── Follow-up Sequences ──
    
    def _validate_sequence_steps(self, steps: List[Dict]) -> None:
        if not isinstance(steps, list) or not steps:
            raise ValueError("sequence steps must be a non-empty list")
        valid_channels = {"email", "slack", "whatsapp"}
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError(f"sequence step {index} must be an object")
            delay = step.get("delay_hours")
            if isinstance(delay, bool) or not isinstance(delay, (int, float)) or not math.isfinite(delay) or delay < 0 or delay > 8760:
                raise ValueError(f"sequence step {index} has invalid delay_hours")
            template_id = step.get("template_id")
            if not isinstance(template_id, str) or template_id not in self.templates.templates:
                raise ValueError(f"sequence step {index} has an unknown template_id")
            channel = step.get("channel")
            if channel is not None and channel not in valid_channels:
                raise ValueError(f"sequence step {index} has an invalid channel")
            if "variables" in step and not isinstance(step["variables"], dict):
                raise ValueError(f"sequence step {index} variables must be an object")

    def create_sequence(self, client_id: str, name: str, steps: List[Dict]) -> FollowUpSequence:
        """Create a bounded, validated follow-up sequence."""
        if not self.get_client(client_id):
            raise ValueError(f"Client {client_id} not found")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("sequence name must be non-empty")
        self._validate_sequence_steps(steps)
        sequence = FollowUpSequence(
            id=str(uuid.uuid4())[:8], name=name, client_id=client_id, steps=copy.deepcopy(steps),
            next_run=(datetime.now(timezone.utc) + timedelta(hours=steps[0]["delay_hours"])).isoformat(),
        )
        self.sequences[sequence.id] = sequence
        self._save_data()
        self._audit("sequence_created", "user", sequence.id, "success", {"client": client_id, "name": name, "steps": len(steps)})
        return sequence

    async def process_sequences(self):
        """Create approval requests for due steps; never bypass the approval gate."""
        now = datetime.now(timezone.utc)
        for seq in self.sequences.values():
            if seq.status != "active" or not seq.next_run:
                continue
            next_run = datetime.fromisoformat(seq.next_run)
            if next_run > now:
                continue
            if seq.pending_approval_id:
                pending = self.approval.get(seq.pending_approval_id)
                if pending and pending.get("status") == "approved":
                    result = await self.dispatch_approved(seq.pending_approval_id)
                    if result.get("success") and result.get("status") in {"sent", "dry_run"}:
                        self._advance_sequence(seq, now)
                        seq.pending_approval_id = None
                elif pending and pending.get("status") == "rejected":
                    seq.status = "paused"
                continue
            step = seq.steps[seq.current_step]
            result = await self.send_message(
                client_id=seq.client_id, template_id=step["template_id"],
                variables=step.get("variables", {}), channel=step.get("channel"),
            )
            if result.get("approval_required"):
                seq.pending_approval_id = result["approval_id"]
        self._save_data()

    def _advance_sequence(self, seq: FollowUpSequence, now: datetime) -> None:
        seq.current_step += 1
        if seq.current_step >= len(seq.steps):
            seq.status = "completed"
            seq.next_run = None
        else:
            seq.next_run = (now + timedelta(hours=seq.steps[seq.current_step]["delay_hours"])).isoformat()

    # ── Scheduler ──
    
    async def start_scheduler(self):
        """Start background scheduler."""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def stop_scheduler(self):
        """Stop background scheduler."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
    
    async def _scheduler_loop(self):
        """Background scheduler loop."""
        while self._running:
            try:
                await self.process_sequences()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Scheduler error: {e}")
                await asyncio.sleep(60)
    
    # ── Analytics ──
    
    def get_stats(self) -> Dict:
        """Get usage statistics."""
        total_messages = len(self.messages)
        sent = sum(1 for m in self.messages.values() if m.status == "sent")
        failed = sum(1 for m in self.messages.values() if m.status == "failed")
        
        by_channel = {}
        for m in self.messages.values():
            by_channel[m.channel] = by_channel.get(m.channel, 0) + 1
        
        return {
            "total_clients": len(self.clients),
            "total_messages": total_messages,
            "sent": sent,
            "failed": failed,
            "success_rate": sent / total_messages if total_messages > 0 else 0,
            "by_channel": by_channel,
            "active_sequences": sum(1 for s in self.sequences.values() if s.status == "active"),
            "templates": len(self.templates.templates),
        }
    
    def get_client_report(self, client_id: str) -> Dict:
        """Get report for a specific client."""
        client = self.get_client(client_id)
        if not client:
            return {"error": "Client not found"}
        
        client_messages = [m for m in self.messages.values() if m.client_id == client_id]
        
        return {
            "client": asdict(client),
            "messages": [asdict(m) for m in client_messages],
            "total_messages": len(client_messages),
            "last_contacted": client.last_contacted,
            "response_rate": client.response_rate,
        }


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Client-Manager-Pro")
    parser.add_argument("command", choices=["send", "client", "template", "sequence", "stats", "report"])
    parser.add_argument("--client-id", help="Client ID")
    parser.add_argument("--client-name", help="Client name")
    parser.add_argument("--client-email", help="Client email")
    parser.add_argument("--template", help="Template ID")
    parser.add_argument("--channel", help="Channel (email/slack/whatsapp)")
    parser.add_argument("--var", action="append", help="Template variable (key=value)")
    parser.add_argument("--storage", default="~/.openclaw/client_manager", help="Storage path")
    
    args = parser.parse_args()
    
    manager = ClientManagerPro(storage_path=args.storage)
    
    if args.command == "client":
        if args.client_name and args.client_email:
            client = manager.add_client(args.client_name, args.client_email)
            print(f"Client added: {client.id}")
        elif args.client_id:
            report = manager.get_client_report(args.client_id)
            print(json.dumps(report, indent=2, default=str))
    
    elif args.command == "send":
        variables = {}
        if args.var:
            for v in args.var:
                k, val = v.split("=", 1)
                variables[k] = val
        
        result = await manager.send_message(
            client_id=args.client_id,
            template_id=args.template,
            variables=variables,
            channel=args.channel
        )
        print(json.dumps(result, indent=2))
    
    elif args.command == "stats":
        print(json.dumps(manager.get_stats(), indent=2))
    
    elif args.command == "template":
        for tid, t in manager.templates.templates.items():
            print(f"{tid}: {t.name} ({t.category}) — used {t.usage_count} times")


if __name__ == "__main__":
    asyncio.run(main())
