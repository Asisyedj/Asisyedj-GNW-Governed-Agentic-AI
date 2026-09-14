import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "prompt_engineering" / "PE_MASTER" / "prompt_mastery.py"
SPEC = importlib.util.spec_from_file_location("prompt_mastery_under_test", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PromptMasterySmokeTests(unittest.TestCase):
    def test_technique_order_and_bounded_build(self):
        config = MODULE.PromptConfig(
            task="offline smoke task",
            role="architect",
            output_format='{"result": "string"}',
            context_files=["offline-context.txt"],
            techniques=[MODULE.TechniqueConfig(technique) for technique in MODULE.Technique],
        )
        generated = MODULE.PromptBuilder().build(config)
        markers = [
            "CONTEXT INJECTION",
            "ROLE ASSIGNMENT",
            "CHAIN-OF-THOUGHT",
            "TREE-OF-THOUGHT",
            "PHASED GENERATION",
            "STRUCTURED OUTPUT",
            "SELF-CRITIQUE LOOP",
        ]
        positions = [generated.text.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('"result": "string"', generated.text)

    def test_numeric_and_schema_validation(self):
        for field, value in (("max_phases", 0), ("max_phases", 6),
                             ("self_critique_rounds", 0), ("self_critique_rounds", 11)):
            config = MODULE.PromptConfig(task="x", techniques=[], **{field: value})
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    MODULE.PromptBuilder().build(config)
        with self.assertRaises(ValueError):
            MODULE.TreeOfThoughtTechnique.apply(MODULE.PromptConfig(), num_paths=0)
        with self.assertRaises(ValueError):
            MODULE.TreeOfThoughtTechnique.apply(MODULE.PromptConfig(), num_paths=11)
        with self.assertRaises(ValueError):
            MODULE.PromptBuilder().build(MODULE.PromptConfig(output_format="not-json"))
            context_files=["offline-context.txt"],
        with self.assertRaises(ValueError):
            MODULE.PromptBuilder().build(MODULE.PromptConfig(output_format="[]"))
            context_files=["offline-context.txt"],

    def test_atomic_output_is_bounded_and_symlink_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "prompt.txt"
            MODULE._atomic_write_text(str(target), "safe output", max_bytes=100)
            self.assertEqual(target.read_text(), "safe output")
            with self.assertRaises(ValueError):
                MODULE._atomic_write_text(str(target), "0123456789", max_bytes=3)
            link = Path(directory) / "link.txt"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                MODULE._atomic_write_text(str(link), "must not replace", max_bytes=100)

    def test_compare_cli_rejects_unimplemented_command(self):
        result = subprocess.run(
            [sys.executable, str(SOURCE), "compare"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not implemented", result.stderr)


if __name__ == "__main__":
    unittest.main()

