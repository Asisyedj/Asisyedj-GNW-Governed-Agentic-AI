"""
Prompt Optimization for Specific AI Models
============================================
Optimized prompts for each model in your stack using the 7 techniques.
"""

import re
import sys
from pathlib import Path


try:
    from prompt_engineering.PE_MASTER.prompt_mastery import (
        PromptBuilder, PromptConfig, TechniqueConfig, Technique,
        ModelTier, TemplateLibrary, PromptEvaluator
    )
except ModuleNotFoundError as exc:
    # Skills are sibling directories rather than installed distributions. Add
    # only the repository's known sibling, resolved from this source file.
    if not (exc.name and exc.name.startswith("prompt_engineering")):
        raise
    _sibling_root = Path(__file__).resolve().parents[2] / "prompt-engineering-mastery"
    if not (_sibling_root / "prompt_engineering" / "PE_MASTER" / "prompt_mastery.py").is_file():
        raise
    if str(_sibling_root) not in sys.path:
        sys.path.insert(0, str(_sibling_root))
    from prompt_engineering.PE_MASTER.prompt_mastery import (
        PromptBuilder, PromptConfig, TechniqueConfig, Technique,
        ModelTier, TemplateLibrary, PromptEvaluator
    )


_PLACEHOLDER_RE = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")


def _validate_context_files(context_files):
    """Validate context references without reading or resolving user files."""
    if context_files is None:
        return []
    if isinstance(context_files, (str, bytes)):
        raise TypeError("context_files must be an iterable of non-empty strings")
    try:
        references = list(context_files)
    except TypeError as exc:
        raise TypeError("context_files must be an iterable of non-empty strings") from exc
    validated = []
    for index, reference in enumerate(references):
        if isinstance(reference, Path):
            reference = str(reference)
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError(f"context_files[{index}] must be a non-empty string")
        if "\x00" in reference:
            raise ValueError(f"context_files[{index}] contains a NUL byte")
        validated.append(reference)
    return validated


def _template_placeholders(template):
    """Return named placeholders while leaving literal JSON braces untouched."""
    return set(_PLACEHOLDER_RE.findall(template))


# ──────────────────────────────────────────────────────────────
# MODEL-SPECIFIC OPTIMIZED PROMPTS
# ──────────────────────────────────────────────────────────────

class ModelPromptOptimizer:
    """Optimize prompts for specific AI models."""
    
    MODEL_PROFILES = {
        "claude-opus-4": {
            "context_window": 200000,
            "strengths": ["reasoning", "analysis", "long_context", "safety"],
            "weaknesses": ["speed", "cost"],
            "best_techniques": [Technique.COT, Technique.PHASED, Technique.CONTEXT, Technique.CRITIQUE],
            "max_phases": 5,
            "critique_rounds": 2,
            "recommended_use": "complex reasoning, research, code architecture",
        },
        "claude-sonnet-4": {
            "context_window": 200000,
            "strengths": ["balance", "speed", "reasoning"],
            "weaknesses": ["very long context"],
            "best_techniques": [Technique.COT, Technique.STRUCTURED, Technique.ROLE],
            "max_phases": 3,
            "critique_rounds": 1,
            "recommended_use": "general purpose, coding, analysis",
        },
        "gpt-4o": {
            "context_window": 128000,
            "strengths": ["structured_output", "json_mode", "speed"],
            "weaknesses": ["reasoning_depth"],
            "best_techniques": [Technique.STRUCTURED, Technique.CRITIQUE, Technique.ROLE],
            "max_phases": 3,
            "critique_rounds": 1,
            "recommended_use": "structured tasks, JSON output, quick analysis",
        },
        "gpt-4o-mini": {
            "context_window": 128000,
            "strengths": ["speed", "cost", "structured_output"],
            "weaknesses": ["complex_reasoning"],
            "best_techniques": [Technique.STRUCTURED, Technique.ROLE, Technique.COT],
            "max_phases": 2,
            "critique_rounds": 1,
            "recommended_use": "simple tasks, classification, routing",
        },
        "gemini-2.5-pro": {
            "context_window": 1000000,
            "strengths": ["massive_context", "multimodal", "research"],
            "weaknesses": ["reasoning_consistency"],
            "best_techniques": [Technique.CONTEXT, Technique.COT, Technique.PHASED],
            "max_phases": 4,
            "critique_rounds": 1,
            "recommended_use": "document analysis, research, multimodal tasks",
        },
        "kimi-k2.5": {
            "context_window": 256000,
            "strengths": ["tool_calls", "stability", "long_context"],
            "weaknesses": ["creativity"],
            "best_techniques": [Technique.PHASED, Technique.COT, Technique.STRUCTURED],
            "max_phases": 5,
            "critique_rounds": 1,
            "recommended_use": "multi-step workflows, tool use, coding",
        },
        "llama3.2-3b": {
            "context_window": 8192,
            "strengths": ["local", "speed", "privacy"],
            "weaknesses": ["reasoning", "context_length"],
            "best_techniques": [Technique.ROLE, Technique.COT, Technique.STRUCTURED],
            "max_phases": 1,
            "critique_rounds": 0,
            "recommended_use": "local classification, simple Q&A, routing",
        },
        "qwen2.5-7b": {
            "context_window": 32768,
            "strengths": ["local", "coding", "reasoning"],
            "weaknesses": ["english_nuance"],
            "best_techniques": [Technique.COT, Technique.STRUCTURED, Technique.ROLE],
            "max_phases": 2,
            "critique_rounds": 0,
            "recommended_use": "local coding, analysis, simple reasoning",
        },
    }
    
    def __init__(self):
        self.builder = PromptBuilder()
    
    def optimize_for_model(self, task: str, model: str, role: str = "engineer",
                          context_files: list = None) -> dict:
        """Generate a model-optimized prompt after validating references."""
        if not isinstance(model, str) or not model.strip():
            return {"error": "model must be a non-empty string"}
        if not isinstance(task, str) or not task.strip():
            return {"error": "task must be a non-empty string"}
        profile = self.MODEL_PROFILES.get(model.lower())
        
        if not profile:
            return {"error": f"Unknown model: {model}. Available: {list(self.MODEL_PROFILES.keys())}"}
        
        # Build config. Context references are identifiers only; this method
        # deliberately does not read them or perform any provider I/O.
        config = PromptConfig(
            role=role,
            task=task,
            context_files=_validate_context_files(context_files),
            techniques=[
                TechniqueConfig(t, enabled=t in profile["best_techniques"])
                for t in Technique
            ],
            model_tier=self._get_tier(profile),
            max_phases=profile["max_phases"],
            self_critique_rounds=profile["critique_rounds"],
        )
        
        # Generate prompt
        prompt = self.builder.build(config)
        
        # Evaluate
        evaluation = PromptEvaluator.evaluate(prompt)
        
        return {
            "model": model,
            "profile": profile,
            "prompt": prompt.text,
            "techniques_used": prompt.techniques_used,
            "estimated_tokens": prompt.estimated_tokens,
            "evaluation": evaluation,
            "recommendations": self._get_recommendations(model, task, profile),
        }
    
    def _get_tier(self, profile: dict) -> ModelTier:
        """Determine model tier from profile."""
        if profile["context_window"] >= 200000:
            return ModelTier.DEEP
        elif profile["context_window"] >= 32000:
            return ModelTier.STANDARD
        else:
            return ModelTier.FAST
    
    def _get_recommendations(self, model: str, task: str, profile: dict) -> list:
        """Get model-specific recommendations."""
        recs = []
        
        if "json" in task.lower() or "structured" in task.lower():
            if Technique.STRUCTURED not in profile["best_techniques"]:
                recs.append(f"Consider using {model} with JSON mode for structured output")
        
        if "code" in task.lower() or "implement" in task.lower():
            if "claude" in model.lower() or "kimi" in model.lower():
                recs.append("Enable phased generation for large codebases")
        
        if "research" in task.lower() or "analyze" in task.lower():
            if profile["context_window"] < 100000:
                recs.append(f"Warning: {model} has limited context for deep research")
        
        if not profile["critique_rounds"]:
            recs.append("Consider adding self-critique for higher quality")
        
        return recs
    
    def compare_models(self, task: str, models: list = None) -> dict:
        """Compare prompt optimization across models without empty-set crashes."""
        if models is None:
            models_to_compare = list(self.MODEL_PROFILES.keys())
        elif isinstance(models, str):
            models_to_compare = [models]
        else:
            try:
                models_to_compare = list(models)
            except TypeError as exc:
                raise TypeError("models must be an iterable of model names") from exc

        comparison = {}
        for model in models_to_compare:
            result = self.optimize_for_model(task, model)
            if "error" not in result:
                comparison[model] = {
                    "techniques": result["techniques_used"],
                    "tokens": result["estimated_tokens"],
                    "grade": result["evaluation"]["grade"],
                    "score": result["evaluation"]["overall_score"],
                }

        result = {
            "task": task,
            "comparison": comparison,
            "best_for_speed": None,
            "best_for_quality": None,
        }
        if comparison:
            result["best_for_speed"] = min(comparison.items(), key=lambda x: x[1]["tokens"])[0]
            result["best_for_quality"] = max(comparison.items(), key=lambda x: x[1]["score"])[0]
        else:
            result["error"] = "No valid models were provided for comparison"
        return result
    
    def get_model_for_task(self, task_type: str) -> str:
        """Recommend best model for task type."""
        task_lower = task_type.lower()
        
        if any(w in task_lower for w in ["research", "analysis", "deep", "complex"]):
            return "claude-opus-4"
        elif any(w in task_lower for w in ["code", "implement", "build", "develop"]):
            return "kimi-k2.5"
        elif any(w in task_lower for w in ["json", "structured", "extract", "parse"]):
            return "gpt-4o"
        elif any(w in task_lower for w in ["document", "long", "multimodal", "image"]):
            return "gemini-2.5-pro"
        elif any(w in task_lower for w in ["quick", "simple", "classify", "route"]):
            return "gpt-4o-mini"
        elif any(w in task_lower for w in ["local", "private", "offline"]):
            return "llama3.2-3b"
        else:
            return "claude-sonnet-4"


# ──────────────────────────────────────────────────────────────
# PRE-OPTIMIZED PROMPTS FOR COMMON TASKS
# ──────────────────────────────────────────────────────────────

class OptimizedPromptLibrary:
    """Library of pre-optimized prompts for common tasks."""
    
    PROMPTS = {
        "code_review": {
            "claude-opus-4": """You are a senior software architect with 20+ years of experience.

╔══════════════════════════════════════════════════════════╗
║                  CHAIN-OF-THOUGHT                        ║
╚══════════════════════════════════════════════════════════╝

Before producing any output, think through these steps IN ORDER:

  1. Read and understand the entire codebase structure
  2. Identify security vulnerabilities (OWASP Top 10)
  3. Check for performance bottlenecks
  4. Review error handling and edge cases
  5. Assess maintainability and documentation
  6. Verify test coverage

For each step:
1. State what you're analyzing
2. Show your reasoning
3. Note any assumptions
4. Identify potential issues

╔══════════════════════════════════════════════════════════╗
║                 PHASED GENERATION                        ║
╚══════════════════════════════════════════════════════════╝

PHASE 1: Architecture Analysis — overall structure, patterns, dependencies
PHASE 2: Security Review — vulnerabilities, injection points, auth issues
PHASE 3: Performance Review — bottlenecks, N+1 queries, memory leaks
PHASE 4: Code Quality — naming, documentation, test coverage
PHASE 5: Recommendations — prioritized action items

Complete each phase fully before moving to the next.

╔══════════════════════════════════════════════════════════╗
║                   SELF-CRITIQUE LOOP                     ║
╚══════════════════════════════════════════════════════════╝

After generating your review:
1. Find 3 weaknesses in your analysis
2. Check for hallucinated issues
3. Verify all line numbers and code references
4. Produce final improved version

TASK: Review the following codebase for production readiness.

{codebase}

QUALITY STANDARD:
  ✓ Every issue must reference specific code
  ✓ Every recommendation must be actionable
  ✓ No false positives
  ✓ Prioritized by severity (P0-P3)

BEGIN.""",
            
            "gpt-4o": """You are a senior software engineer reviewing code for production.

Respond ONLY in this exact JSON schema:
{
  "security_issues": [{"severity": "P0|P1|P2", "description": "string", "line": "number", "fix": "string"}],
  "performance_issues": [{"severity": "P0|P1|P2", "description": "string", "line": "number", "fix": "string"}],
  "quality_issues": [{"severity": "P0|P1|P2", "description": "string", "line": "number", "fix": "string"}],
  "overall_score": "number 0-100",
  "recommendation": "string — approve|request_changes|reject"
}

Do NOT include any text outside the JSON.

Code to review:
{codebase}""",
            
            "kimi-k2.5": """You are a senior software engineer. Review this code systematically.

PHASE 1: Security scan — find vulnerabilities
PHASE 2: Performance scan — find bottlenecks
PHASE 3: Quality scan — find maintainability issues

After each phase, STOP and verify findings.

Code:
{codebase}""",
        },
        
        "research_synthesis": {
            "gemini-2.5-pro": """You are a PhD-level research scientist with expertise in systematic literature review.

╔══════════════════════════════════════════════════════════╗
║                 CONTEXT INJECTION                        ║
╚══════════════════════════════════════════════════════════╝

The following papers are the AUTHORITATIVE source of truth:

{papers}

RULES:
- Treat these papers as the ABSOLUTE contract
- Do NOT invent claims not supported by these papers
- If anything is ambiguous, state your assumption explicitly
- Reference specific sections when making claims
- Quote relevant passages when justifying analysis

╔══════════════════════════════════════════════════════════╗
║                  CHAIN-OF-THOUGHT                        ║
╚══════════════════════════════════════════════════════════╝

Before producing any output, think through these steps IN ORDER:

  1. Identify the main research question across all papers
  2. Extract key findings from each paper
  3. Map agreements and contradictions
  4. Identify gaps in current knowledge
  5. Synthesize a unified framework

╔══════════════════════════════════════════════════════════╗
║                   TREE-OF-THOUGHT                        ║
╚══════════════════════════════════════════════════════════╝

Generate 3 different synthesis approaches:

  Approach 1: Chronological — how understanding evolved
  Approach 2: Thematic — group by topic/methodology
  Approach 3: Contradiction-focused — resolve conflicts

For EACH approach:
  - Describe the structure
  - List pros and cons
  - Identify which papers fit best
  - Estimate completeness (0-100%)

Then select the best approach with justification.

╔══════════════════════════════════════════════════════════╗
║                   SELF-CRITIQUE LOOP                     ║
╚══════════════════════════════════════════════════════════╝

After generating your synthesis:
1. Find 3 unsupported claims
2. Check for missed contradictions
3. Verify all citations map to actual papers
4. Produce final improved version

TASK: Synthesize the provided papers into a comprehensive literature review.

QUALITY STANDARD:
  ✓ Every claim maps to a specific paper
  ✓ All contradictions explicitly addressed
  ✓ Gaps clearly identified
  ✓ Publication-ready quality

BEGIN.""",
        },
        
        "client_communication": {
            "claude-sonnet-4": """You are a senior client success manager with 12+ years of experience in SaaS and professional services.

Your communication style:
- Professional but warm
- Concise and action-oriented
- Focused on client value
- Never pushy or salesy

TASK: Draft a client communication for the following scenario:

{scenario}

Requirements:
1. Clear subject line (under 60 characters)
2. Personalized opening (reference specific detail)
3. Value proposition (what's in it for them)
4. Clear call-to-action (one specific next step)
5. Professional signature

Tone: {tone}
Urgency: {urgency}

Generate the complete email.""",
        },
        
        "data_analysis": {
            "gpt-4o": """You are a senior data analyst with expertise in statistical modeling and business intelligence.

Respond ONLY in this exact JSON schema:
{
  "summary_statistics": {
    "count": "number",
    "mean": "number",
    "median": "number",
    "std_dev": "number",
    "min": "number",
    "max": "number"
  },
  "key_insights": ["string — insight 1", "string — insight 2", "string — insight 3"],
  "anomalies": [{"description": "string", "severity": "low|medium|high"}],
  "recommendations": [{"action": "string", "priority": "P0|P1|P2", "expected_impact": "string"}],
  "confidence": "number 0-1",
  "visualization_suggestions": ["string — chart type for each insight"]
}

Data to analyze:
{data}

Analysis question:
{question}""",
        },
        
        "local_classification": {
            "llama3.2-3b": """You are a helpful assistant. Classify the following input into one of these categories:

Categories: {categories}

Input: {input}

Respond with ONLY the category name, nothing else.""",
        },
    }
    
    @classmethod
    def get_prompt(cls, task: str, model: str, **kwargs) -> str:
        """Get an exact library prompt; never silently substitute another model."""
        task_prompts = cls.PROMPTS.get(task)
        if not task_prompts:
            raise KeyError(f"Unknown prompt task: {task}")
        prompt = task_prompts.get(model)
        if prompt is None:
            raise KeyError(f"No prompt for model {model!r} and task {task!r}")

        required = _template_placeholders(prompt)
        supplied = set(kwargs)
        missing = sorted(required - supplied)
        unexpected = sorted(supplied - required)
        if missing:
            raise ValueError(f"Missing prompt placeholders: {', '.join(missing)}")
        if unexpected:
            raise ValueError(f"Unknown prompt placeholders: {', '.join(unexpected)}")

        for key, value in kwargs.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        unresolved = sorted(_template_placeholders(prompt))
        if unresolved:
            raise ValueError(f"Unresolved prompt placeholders: {', '.join(unresolved)}")
        return prompt


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Prompt Optimization for AI Models")
    parser.add_argument("command", choices=["optimize", "compare", "recommend", "library"])
    parser.add_argument("--task", help="Task description")
    parser.add_argument("--model", help="Target model")
    parser.add_argument("--role", default="engineer", help="Expert role")
    parser.add_argument("--models", nargs="*", help="Models to compare")
    parser.add_argument("--task-type", help="Task type for recommendation")
    parser.add_argument(
        "--show-prompt", action="store_true",
        help="Explicitly print the generated prompt (withheld by default)",
    )
    
    args = parser.parse_args()
    
    optimizer = ModelPromptOptimizer()
    
    if args.command == "optimize":
        if not args.task or not args.model:
            print("Error: --task and --model required")
            return
        
        result = optimizer.optimize_for_model(args.task, args.model, args.role)
        
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        
        print(f"Model: {result['model']}")
        print(f"Techniques: {', '.join(result['techniques_used'])}")
        print(f"Estimated tokens: {result['estimated_tokens']}")
        print(f"Grade: {result['evaluation']['grade']}")
        print()
        if args.show_prompt:
            print("Optimized Prompt:")
            print("="*60)
            print(result['prompt'])
        else:
            print("Optimized prompt withheld; pass --show-prompt to display it.")
        
        if result['recommendations']:
            print()
            print("Recommendations:")
            for rec in result['recommendations']:
                print(f"  • {rec}")
    
    elif args.command == "compare":
        if not args.task:
            print("Error: --task required")
            return
        
        result = optimizer.compare_models(args.task, args.models)
        
        print(f"Task: {result['task']}")
        print(f"Best for speed: {result['best_for_speed']}")
        print(f"Best for quality: {result['best_for_quality']}")
        print()
        print("Comparison:")
        for model, data in result['comparison'].items():
            print(f"  {model}: {data['grade']} ({data['score']:.2f}) — {data['tokens']} tokens")
    
    elif args.command == "recommend":
        if not args.task_type:
            print("Error: --task-type required")
            return
        
        model = optimizer.get_model_for_task(args.task_type)
        print(f"Recommended model for '{args.task_type}': {model}")
        
        profile = optimizer.MODEL_PROFILES.get(model, {})
        print(f"  Context: {profile.get('context_window', 'N/A')} tokens")
        print(f"  Best for: {profile.get('recommended_use', 'N/A')}")
    
    elif args.command == "library":
        print("Available pre-optimized prompts:")
        for task, models in OptimizedPromptLibrary.PROMPTS.items():
            print(f"\n  {task}:")
            for model in models.keys():
                print(f"    • {model}")


if __name__ == "__main__":
    main()
