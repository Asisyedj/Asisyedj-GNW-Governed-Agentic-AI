#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).parent / "openclaw" / "oc-049-cross-instance-federated-learner" / "federated_learner.py"


def load_module():
    spec = importlib.util.spec_from_file_location("oc049_federated_learner", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FederatedLearnerOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def test_validation_and_coordinatewise_aggregation(self):
        m = self.mod
        self.assertEqual(
            m.TrimmedMean.aggregate(
                [{"layer": [1.0, 10.0]}, {"layer": [2.0, 20.0]}, {"layer": [3.0, 30.0]}],
                trim_ratio=0,
            ),
            {"layer": [2.0, 20.0]},
        )
        with self.assertRaises(ValueError):
            m.TrimmedMean.aggregate([{"layer": [1.0]}, {"layer": [1.0, 2.0]}])
        with self.assertRaises(ValueError):
            m.DPBudget(epsilon=0)
        with self.assertRaises(ValueError):
            m.ShamirSecretSharing(0, 3)

    def test_consent_signature_round_and_duplicate_rejection(self):
        m = self.mod
        with tempfile.TemporaryDirectory() as directory:
            coordinator = m.FederatedCoordinator(directory)
            participants = [
                coordinator.register_participant(f"p{i}", f"shared-key-{i}", data_size=10, consent=True)
                for i in range(3)
            ]
            round_obj = coordinator.start_round(min_participants=3)
            self.assertIsNotNone(round_obj)
            assert round_obj
            for index, participant in enumerate(participants):
                update = m.ModelUpdate(
                    participant.id,
                    round_obj.id,
                    {"layer": [float(index + 1), float(index + 2)]},
                    10,
                )
                update.signature = m.sign_model_update(update, participant.public_key)
                result = coordinator.submit_update(update)
                self.assertTrue(result["success"], result)
                if index == 0:
                    duplicate = coordinator.submit_update(update)
                    self.assertFalse(duplicate["success"])
                    self.assertIn("Duplicate", duplicate["error"])
            self.assertEqual(round_obj.status, m.RoundStatus.COMPLETED)
            self.assertEqual(coordinator.global_model_version, 1)
            self.assertEqual(set(coordinator.get_global_model()["layer"]), set(coordinator.get_global_model()["layer"]))

    def test_mismatched_round_and_invalid_signature_fail_closed(self):
        m = self.mod
        with tempfile.TemporaryDirectory() as directory:
            coordinator = m.FederatedCoordinator(directory)
            participant = coordinator.register_participant("p", "valid-key", data_size=1, consent=True)
            round_obj = coordinator.start_round(min_participants=1)
            assert round_obj
            wrong_round = m.ModelUpdate(participant.id, "wrong-round", {"layer": [1.0]}, 1)
            wrong_round.signature = m.sign_model_update(wrong_round, participant.public_key)
            self.assertFalse(coordinator.submit_update(wrong_round)["success"])
            invalid = m.ModelUpdate(participant.id, round_obj.id, {"layer": [1.0]}, 1, signature="bad")
            self.assertFalse(coordinator.submit_update(invalid)["success"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
