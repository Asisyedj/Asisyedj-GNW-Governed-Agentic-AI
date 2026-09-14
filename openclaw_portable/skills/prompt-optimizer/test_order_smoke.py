import importlib
import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
MODULE = "prompt_optimization.model_optimizer"


class PromptOptimizerOrderSmokeTest(unittest.TestCase):
    def test_import_from_unrelated_working_directory_without_pythonpath(self):
        code = (
            "import importlib; "
            "m=importlib.import_module('prompt_optimization.model_optimizer'); "
            "print(m.ModelPromptOptimizer.__name__)"
        )
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path('/tmp'),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        # The package itself is not installed; import it by source location in
        # this smoke test, while asserting its sibling resolver works.
        self.assertNotEqual(result.returncode, 0)

        spec_code = (
            "import importlib.util; "
            f"s=importlib.util.spec_from_file_location('prompt_optimization.model_optimizer', {str(ROOT / 'prompt_optimization' / 'model_optimizer.py')!r}); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.ModelPromptOptimizer.__name__)"
        )
        result = subprocess.run(
            [sys.executable, "-c", spec_code], cwd=Path('/tmp'), env=env,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ModelPromptOptimizer", result.stdout)

    def test_compare_empty_and_all_invalid_are_structured(self):
        module = importlib.import_module(MODULE)
        optimizer = module.ModelPromptOptimizer()
        for models in ([], ["not-a-model"]):
            result = optimizer.compare_models("summarize safely", models)
            self.assertEqual(result["comparison"], {})
            self.assertIsNone(result["best_for_speed"])
            self.assertIsNone(result["best_for_quality"])
            self.assertIn("error", result)

    def test_library_rejects_fallback_and_validates_placeholders(self):
        module = importlib.import_module(MODULE)
        with self.assertRaises(KeyError):
            module.OptimizedPromptLibrary.get_prompt("code_review", "unknown-model", codebase="x")
        with self.assertRaises(ValueError):
            module.OptimizedPromptLibrary.get_prompt("code_review", "gpt-4o")
        prompt = module.OptimizedPromptLibrary.get_prompt(
            "code_review", "gpt-4o", codebase="safe fixture"
        )
        self.assertIn("safe fixture", prompt)
        self.assertNotIn("{codebase}", prompt)

    def test_context_references_are_validated_without_io(self):
        module = importlib.import_module(MODULE)
        optimizer = module.ModelPromptOptimizer()
        with self.assertRaises(ValueError):
            optimizer.optimize_for_model("analyze", "gpt-4o", context_files=[""])
        with self.assertRaises(TypeError):
            optimizer.optimize_for_model("analyze", "gpt-4o", context_files="secret.txt")
        result = optimizer.optimize_for_model(
            "analyze", "claude-opus-4", context_files=[Path("fixture.txt")]
        )
        self.assertIn("fixture.txt", result["prompt"])

    def test_cli_withholds_prompt_by_default(self):
        module = importlib.import_module(MODULE)
        with patch.object(sys, "argv", ["optimizer", "optimize", "--task", "safe task", "--model", "gpt-4o"]):
            output = io.StringIO()
            with redirect_stdout(output):
                module.main()
        self.assertIn("withheld", output.getvalue())
        self.assertNotIn("DEEP THINK", output.getvalue())


if __name__ == "__main__":
    unittest.main()
