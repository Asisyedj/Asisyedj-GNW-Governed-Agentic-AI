"""Cross-instance federated learner (OC-049), offline stdlib implementation."""
import asyncio
import hashlib
import hmac
import json
import math
import secrets
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAX_LAYERS = 10_000
MAX_VALUES_PER_LAYER = 1_000_000
MAX_SAMPLES = 10_000_000


def _count(value: Any, name: str, minimum: int = 0, maximum: int = MAX_SAMPLES) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def _weights(weights: Any, nonempty: bool = True) -> Dict[str, List[float]]:
    if not isinstance(weights, dict) or len(weights) > MAX_LAYERS or (nonempty and not weights):
        raise ValueError("weights has an invalid number of layers")
    result: Dict[str, List[float]] = {}
    for layer, values in weights.items():
        if not isinstance(layer, str) or not layer or not isinstance(values, list) or not values or len(values) > MAX_VALUES_PER_LAYER:
            raise ValueError(f"layer {layer!r} has an invalid shape")
        result[layer] = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError(f"layer {layer!r} contains a non-finite numeric value")
            result[layer].append(float(value))
    return result


def _key(key: Any) -> bytes:
    value = key if isinstance(key, bytes) else key.encode("utf-8") if isinstance(key, str) else b""
    if not value:
        raise ValueError("signing key must be non-empty bytes or text")
    return value


def _payload(update: Any) -> bytes:
    data = asdict(update) if isinstance(update, ModelUpdate) else dict(update)
    data.pop("signature", None)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sign_model_update(update: Any, signing_key: Any) -> str:
    """HMAC-SHA256 integrity/authentication, not an asymmetric signature."""
    return hmac.new(_key(signing_key), _payload(update), hashlib.sha256).hexdigest()


def verify_model_update_signature(update: Any, signing_key: Any) -> bool:
    supplied = update.signature if isinstance(update, ModelUpdate) else dict(update).get("signature", "")
    if not isinstance(supplied, str) or not supplied:
        return False
    try:
        return hmac.compare_digest(supplied, sign_model_update(update, signing_key))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False


class ParticipantStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    COMPLETED = "completed"


class RoundStatus:
    PENDING = "pending"
    COLLECTING = "collecting"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Participant:
    id: str
    name: str
    public_key: str
    status: str = "active"
    joined_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rounds_participated: int = 0
    data_size: int = 0
    dp_budget_used: float = 0.0
    consent_given: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelUpdate:
    participant_id: str
    round_id: str
    weights: Dict[str, List[float]]
    num_samples: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    signature: str = ""
    dp_noise_added: bool = False


@dataclass
class TrainingRound:
    id: str
    round_number: int
    status: str = "pending"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    participants: List[str] = field(default_factory=list)
    updates_received: int = 0
    aggregated_weights: Optional[Dict] = None
    global_model_version: int = 0


@dataclass
class DPBudget:
    epsilon: float = 1.0
    delta: float = 1e-5
    total_epsilon: float = 10.0
    spent_epsilon: float = 0.0

    def __post_init__(self):
        values = (self.epsilon, self.delta, self.total_epsilon, self.spent_epsilon)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError("DP parameters must be finite numbers")
        if self.epsilon <= 0 or not 0 < self.delta < 1 or self.total_epsilon <= 0 or not 0 <= self.spent_epsilon <= self.total_epsilon:
            raise ValueError("invalid DP budget parameters")

    def can_spend(self, amount: float) -> bool:
        return isinstance(amount, (int, float)) and not isinstance(amount, bool) and math.isfinite(amount) and amount >= 0 and self.spent_epsilon + amount <= self.total_epsilon

    def spend(self, amount: float) -> bool:
        if self.can_spend(amount):
            self.spent_epsilon += amount
            return True
        return False

    def remaining(self) -> float:
        return self.total_epsilon - self.spent_epsilon


class ShamirSecretSharing:
    """Small-field Shamir helper with strict threshold and share validation."""
    def __init__(self, threshold: int, num_shares: int):
        self.prime = 2**127 - 1
        if isinstance(threshold, bool) or not isinstance(threshold, int) or isinstance(num_shares, bool) or not isinstance(num_shares, int) or threshold < 2 or num_shares < threshold or num_shares >= self.prime:
            raise ValueError("require 2 <= threshold <= num_shares < prime")
        self.threshold, self.num_shares = threshold, num_shares

    def _evaluate(self, coefficients: List[int], x: int) -> int:
        return sum(c * pow(x, i, self.prime) for i, c in enumerate(coefficients)) % self.prime

    def split(self, secret: int) -> List[Tuple[int, int]]:
        if isinstance(secret, bool) or not isinstance(secret, int) or not 0 <= secret < self.prime:
            raise ValueError("secret must be an integer in the Shamir field")
        coefficients = [secret] + [secrets.randbelow(self.prime) for _ in range(self.threshold - 1)]
        return [(x, self._evaluate(coefficients, x)) for x in range(1, self.num_shares + 1)]

    def reconstruct(self, shares: List[Tuple[int, int]]) -> int:
        if not isinstance(shares, list) or len(shares) < self.threshold:
            raise ValueError(f"Need at least {self.threshold} shares")
        selected, seen = shares[:self.threshold], set()
        for share in selected:
            if not isinstance(share, (tuple, list)) or len(share) != 2:
                raise ValueError("shares must be (x, y) pairs")
            x, y = share
            if isinstance(x, bool) or not isinstance(x, int) or not 0 < x < self.prime or isinstance(y, bool) or not isinstance(y, int) or not 0 <= y < self.prime or x in seen:
                raise ValueError("invalid or duplicate Shamir share")
            seen.add(x)
        secret = 0
        for i, (x_i, y_i) in enumerate(selected):
            numerator, denominator = 1, 1
            for j, (x_j, _) in enumerate(selected):
                if i != j:
                    numerator = numerator * (-x_j) % self.prime
                    denominator = denominator * (x_i - x_j) % self.prime
            secret = (secret + y_i * numerator * pow(denominator, -1, self.prime)) % self.prime
        return secret


class DifferentialPrivacy:
    @staticmethod
    def add_gaussian_noise(value: float, sensitivity: float, epsilon: float, delta: float) -> float:
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (value, sensitivity, epsilon, delta)) or sensitivity < 0 or epsilon <= 0 or not 0 < delta < 1:
            raise ValueError("invalid DP parameters")
        sigma = sensitivity * math.sqrt(2 * math.log(1.25 / delta)) / epsilon
        return value + secrets.SystemRandom().gauss(0, sigma)

    @staticmethod
    def clip_gradient(gradient: Dict[str, List[float]], max_norm: float) -> Dict[str, List[float]]:
        if isinstance(max_norm, bool) or not isinstance(max_norm, (int, float)) or not math.isfinite(max_norm) or max_norm <= 0:
            raise ValueError("max_norm must be positive and finite")
        gradient = _weights(gradient)
        total_norm = math.sqrt(sum(v * v for values in gradient.values() for v in values))
        if total_norm > max_norm:
            scale = max_norm / total_norm
            return {layer: [v * scale for v in values] for layer, values in gradient.items()}
        return gradient


class TrimmedMean:
    @staticmethod
    def aggregate(updates: List[Dict[str, List[float]]], trim_ratio: float = 0.2) -> Dict[str, List[float]]:
        """Coordinate-wise trimmed mean; input layer shapes must match."""
        if not updates:
            return {}
        if isinstance(trim_ratio, bool) or not isinstance(trim_ratio, (int, float)) or not math.isfinite(trim_ratio) or not 0 <= trim_ratio < 0.5:
            raise ValueError("trim_ratio must be finite and in [0, 0.5)")
        checked = [_weights(update) for update in updates]
        layers = list(checked[0])
        if any(set(u) != set(layers) for u in checked) or any(any(len(u[layer]) != len(checked[0][layer]) for layer in layers) for u in checked[1:]):
            raise ValueError("all updates must have identical layer shapes")
        trim = int(len(checked) * trim_ratio)
        result = {}
        for layer in layers:
            result[layer] = []
            for i in range(len(checked[0][layer])):
                values = sorted(u[layer][i] for u in checked)
                kept = values[trim:len(values)-trim] if trim else values
                result[layer].append(sum(kept) / len(kept))
        return result


class FederatedCoordinator:
    def __init__(self, storage_path: str = "~/.openclaw/federated"):
        self.storage_path = Path(storage_path).expanduser()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.participants: Dict[str, Participant] = {}
        self.rounds: Dict[str, TrainingRound] = {}
        self.current_round: Optional[str] = None
        self.global_model_version = 0
        self.dp_budget = DPBudget()
        self.shamir = ShamirSecretSharing(3, 5)
        self.audit_log: List[Dict] = []
        self._load_state()

    def _load_state(self):
        state = self.storage_path / "coordinator.json"
        if state.exists():
            data = json.loads(state.read_text())
            self.global_model_version = data.get("global_model_version", 0)
            self.dp_budget.spent_epsilon = data.get("dp_spent", 0.0)
            self.dp_budget.__post_init__()

    def _save_state(self):
        (self.storage_path / "coordinator.json").write_text(json.dumps({"global_model_version": self.global_model_version, "dp_spent": self.dp_budget.spent_epsilon, "updated_at": datetime.now(timezone.utc).isoformat()}, indent=2))

    def _audit(self, action: str, actor: str, target: str, result: str, metadata: Dict = None):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "action": action, "actor": actor, "target": target, "result": result, "metadata": metadata or {}, "audit_id": str(uuid.uuid4())[:8]}
        self.audit_log.append(entry)
        with (self.storage_path / "audit.jsonl").open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def register_participant(self, name: str, public_key: str, data_size: int = 0, consent: bool = False) -> Participant:
        if not consent:
            raise ValueError("explicit participant consent is required")
        _key(public_key)
        _count(data_size, "data_size")
        participant = Participant(str(uuid.uuid4())[:8], name, public_key, data_size=data_size, consent_given=True)
        self.participants[participant.id] = participant
        self._audit("participant_registered", "coordinator", participant.id, "success", {"name": name, "data_size": data_size})
        return participant

    def get_active_participants(self) -> List[Participant]:
        return [p for p in self.participants.values() if p.status == "active" and p.consent_given]

    def start_round(self, min_participants: int = 3) -> Optional[TrainingRound]:
        _count(min_participants, "min_participants", 1, MAX_LAYERS)
        active = self.get_active_participants()
        if len(active) < min_participants or not self.dp_budget.can_spend(self.dp_budget.epsilon):
            self._audit("round_failed", "coordinator", "new_round", "insufficient_participants_or_dp_budget")
            return None
        rid = str(uuid.uuid4())[:8]
        round_obj = TrainingRound(rid, len(self.rounds) + 1, RoundStatus.COLLECTING, datetime.now(timezone.utc).isoformat(), participants=[p.id for p in active])
        self.rounds[rid], self.current_round = round_obj, rid
        self._audit("round_started", "coordinator", rid, "success", {"participants": len(active)})
        return round_obj

    def submit_update(self, update: ModelUpdate) -> Dict:
        if not self.current_round:
            return {"success": False, "error": "No active round"}
        round_obj = self.rounds.get(self.current_round)
        if not round_obj or round_obj.status != RoundStatus.COLLECTING:
            return {"success": False, "error": "Round is not collecting"}
        if not isinstance(update, ModelUpdate):
            return {"success": False, "error": "Invalid update type"}
        participant = self.participants.get(update.participant_id)
        if not participant:
            return {"success": False, "error": "Participant not registered"}
        if not participant.consent_given:
            return {"success": False, "error": "Participant consent is required"}
        if participant.id not in round_obj.participants:
            return {"success": False, "error": "Participant not in this round"}
        if update.round_id != round_obj.id:
            return {"success": False, "error": "Mismatched round ID"}
        try:
            _count(update.num_samples, "num_samples", 1)
            update.weights = _weights(update.weights)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        target = self.storage_path / f"update_{round_obj.id}_{participant.id}.json"
        if target.exists():
            return {"success": False, "error": "Duplicate participant update"}
        if not verify_model_update_signature(update, participant.public_key):
            return {"success": False, "error": "Invalid update signature"}
        target.write_text(json.dumps(asdict(update), indent=2, allow_nan=False))
        round_obj.updates_received += 1
        participant.rounds_participated += 1
        participant.last_seen = datetime.now(timezone.utc).isoformat()
        self._audit("update_submitted", participant.id, round_obj.id, "success", {"num_samples": update.num_samples})
        if round_obj.updates_received == len(round_obj.participants):
            self._complete_round(round_obj)
        return {"success": True, "round_id": round_obj.id, "updates_received": round_obj.updates_received}

    def _complete_round(self, round_obj: TrainingRound):
        round_obj.status = RoundStatus.AGGREGATING
        updates = []
        for pid in round_obj.participants:
            file = self.storage_path / f"update_{round_obj.id}_{pid}.json"
            if file.exists():
                updates.append(_weights(json.loads(file.read_text())["weights"]))
        if not updates:
            round_obj.status = RoundStatus.FAILED
            return
        aggregated = TrimmedMean.aggregate(updates)
        noisy = {layer: [DifferentialPrivacy.add_gaussian_noise(v, 1.0, self.dp_budget.epsilon, self.dp_budget.delta) for v in values] for layer, values in aggregated.items()}
        self.dp_budget.spend(self.dp_budget.epsilon)
        self.global_model_version += 1
        round_obj.aggregated_weights, round_obj.status, round_obj.completed_at, round_obj.global_model_version = noisy, RoundStatus.COMPLETED, datetime.now(timezone.utc).isoformat(), self.global_model_version
        self.current_round = None
        (self.storage_path / f"global_model_v{self.global_model_version}.json").write_text(json.dumps(noisy, allow_nan=False))
        self._save_state()
        self._audit("round_completed", "coordinator", round_obj.id, "success", {"global_version": self.global_model_version})

    def get_global_model(self, version: int = None) -> Optional[Dict]:
        version = version or self.global_model_version
        file = self.storage_path / f"global_model_v{version}.json"
        return json.loads(file.read_text()) if file.exists() else None

    def get_status(self) -> Dict:
        return {"global_model_version": self.global_model_version, "total_rounds": len(self.rounds), "active_participants": len(self.get_active_participants()), "total_participants": len(self.participants), "dp_budget": {"spent": self.dp_budget.spent_epsilon, "total": self.dp_budget.total_epsilon, "remaining": self.dp_budget.remaining()}, "current_round": self.current_round, "completed_rounds": sum(r.status == RoundStatus.COMPLETED for r in self.rounds.values())}


class FederatedParticipant:
    def __init__(self, participant_id: str, coordinator_url: str = None, signing_key: Any = None):
        self.participant_id, self.coordinator_url, self.signing_key = participant_id, coordinator_url, signing_key
        self.local_model: Optional[Dict] = None
        self.dp_epsilon, self.dp_delta = 1.0, 1e-5

    def set_local_model(self, weights: Dict[str, List[float]]):
        self.local_model = _weights(weights)

    def train_local(self, local_data: List[Dict], epochs: int = 1) -> ModelUpdate:
        if not self.local_model:
            raise ValueError("No local model set")
        _count(len(local_data), "local_data")
        _count(epochs, "epochs", 1)
        updated = {layer: [v - 0.01 * (hash(str(local_data)) % 100) / 100 for v in values] for layer, values in self.local_model.items()}
        clipped = DifferentialPrivacy.clip_gradient(updated, 1.0)
        noisy = {layer: [DifferentialPrivacy.add_gaussian_noise(v, 1.0, self.dp_epsilon, self.dp_delta) for v in values] for layer, values in clipped.items()}
        return ModelUpdate(self.participant_id, "", noisy, len(local_data), dp_noise_added=True)

    def create_secure_update(self, update: ModelUpdate, round_id: str, signing_key: Any = None) -> Dict:
        if not isinstance(update, ModelUpdate) or not isinstance(round_id, str) or not round_id:
            raise ValueError("invalid update or round ID")
        key = signing_key if signing_key is not None else self.signing_key
        if key is None:
            raise ValueError("a shared signing key is required")
        update.round_id = round_id
        update.weights = _weights(update.weights)
        _count(update.num_samples, "num_samples", 1)
        update.signature = sign_model_update(update, key)
        return asdict(update)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cross-Instance Federated Learner")
    parser.add_argument("command", choices=["coordinator", "participant", "status", "audit"])
    parser.add_argument("--action", choices=["start", "join", "train", "submit", "status"])
    parser.add_argument("--name")
    parser.add_argument("--storage", default="~/.openclaw/federated")
    args = parser.parse_args()
    if args.command == "coordinator" and args.action == "status":
        print(json.dumps(FederatedCoordinator(args.storage).get_status(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())


# Limitation: this module provides a shared-secret HMAC verifier, not full
# asymmetric signatures, TLS, secure transport, or production key management.
# It does not claim those properties.

# compatibility aliases for callers that used the old private terminology
_validate_weights = _weights
_validate_count = _count
_validate_key = _key
_DUMMY = None

def _validate_weights_alias(weights):
    return _weights(weights)


def _validate_count_alias(value, name, minimum=0, maximum=MAX_SAMPLES):
    return _count(value, name, minimum, maximum)
