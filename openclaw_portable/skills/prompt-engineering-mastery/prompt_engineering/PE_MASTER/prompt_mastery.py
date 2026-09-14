"""
Prompt Engineering Mastery System — Core Implementation
==========================================================
The ultimate prompt engineering framework combining 7 world-class techniques.
"""

import json
import os
import re
import tempfile
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


MAX_PHASES = 5
MAX_CRITIQUE_ROUNDS = 10
MAX_TREE_PATHS = 10
MAX_OUTPUT_BYTES = 2 * 1024 * 1024


def _bounded_int(name: str, value: Any, minimum: int, maximum: int) -> int:
    """Validate an integer option without treating booleans as integers."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _validate_output_schema(schema: Union[str, Dict[str, Any]]) -> str:
    """Return a JSON object schema as text, rejecting malformed contracts."""
    if isinstance(schema, str):
        try:
            parsed = json.loads(schema)
        except json.JSONDecodeError as exc:
            raise ValueError("output_format must be valid JSON") from exc
    elif isinstance(schema, dict):
        parsed = schema
    else:
        raise ValueError("output_format must be a JSON object or JSON object string")
    if not isinstance(parsed, dict) or not parsed:
        raise ValueError("output_format must contain a non-empty JSON object")
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def _atomic_write_text(path: str, text: str, max_bytes: int = MAX_OUTPUT_BYTES) -> None:
    """Atomically write bounded UTF-8 text, refusing a symlink destination."""
    if not isinstance(path, str) or not path or "\x00" in path:
        raise ValueError("output path must be a non-empty path without NUL bytes")
    if not isinstance(text, str):
        raise TypeError("output text must be a string")
    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes:
        raise ValueError(f"output exceeds the {max_bytes}-byte limit")
    destination = os.path.abspath(path)
    if os.path.lexists(destination) and os.path.islink(destination):
        raise ValueError("refusing to replace a symbolic-link output path")
    parent = os.path.dirname(destination) or os.curdir
    if not os.path.isdir(parent):
        raise ValueError("output parent directory must already exist")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=parent, prefix=f".{os.path.basename(destination)}.", suffix=".tmp", delete=False) as handle:
            temporary = handle.name
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


# ──────────────────────────────────────────────────────────────
# TECHNIQUE ENUMS & MODELS
# ──────────────────────────────────────────────────────────────

class Technique(Enum):
    ROLE = "role_assignment"
    COT = "chain_of_thought"
    TOT = "tree_of_thought"
    CRITIQUE = "self_critique"
    STRUCTURED = "structured_output"
    PHASED = "phased_generation"
    CONTEXT = "context_injection"


class ModelTier(Enum):
    FAST = "fast"        # Local models, quick classification
    STANDARD = "standard"  # GPT-4o, Claude Sonnet
    DEEP = "deep"        # Claude Opus, Gemini 2.5 Pro, Kimi-K2


@dataclass
class TechniqueConfig:
    technique: Technique
    enabled: bool = True
    weight: float = 1.0  # How strongly to apply
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptConfig:
    role: Optional[str] = None
    domain: Optional[str] = None
    task: str = ""
    constraints: List[str] = field(default_factory=list)
    output_format: Optional[str] = None
    context_files: List[str] = field(default_factory=list)
    techniques: List[TechniqueConfig] = field(default_factory=list)
    model_tier: ModelTier = ModelTier.STANDARD
    max_phases: int = 5
    self_critique_rounds: int = 1


@dataclass
class GeneratedPrompt:
    text: str
    techniques_used: List[str]
    estimated_tokens: int
    model_target: str
    phases: List[str] = field(default_factory=list)
    critique_points: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# TECHNIQUE IMPLEMENTATIONS
# ──────────────────────────────────────────────────────────────

class RoleTechnique:
    """Role Assignment — activates domain-specific reasoning."""
    
    ROLES = {
        "architect": "You are a software architect focused on scalable, maintainable systems.",
        "security": "You are a senior security engineer focused on penetration testing, secure coding, and threat modeling.",
        "researcher": "You are a research scientist with expertise in systematic literature review, experimental design, and statistical analysis.",
        "writer": "You are an technical writer focused on making complex topics accessible.",
        "analyst": "You are a senior data analyst with expertise in statistical modeling, data visualization, and business intelligence.",
        "engineer": "You are a senior software engineer focused on Python, system design, and production deployment.",
        "product": "You are a senior product manager focused on SaaS, user research, and go-to-market strategy.",
        "devops": "You are a senior DevOps engineer with expertise in Kubernetes, CI/CD, infrastructure as code, and cloud architecture.",
    }
    
    @classmethod
    def apply(cls, config: PromptConfig) -> str:
        if not config.role:
            return ""
        
        role_text = cls.ROLES.get(config.role.lower(), 
            f"You are a {config.role} focused on {config.domain or 'your field'}.")
        
        return f"""╔══════════════════════════════════════════════════════════╗
║                    ROLE ASSIGNMENT                        ║
╚══════════════════════════════════════════════════════════╝

{role_text}

Your expertise areas:
- {config.domain or 'General'}
- Deep analytical thinking
- Production-grade output
- Systematic problem solving

"""


class ChainOfThoughtTechnique:
    """Chain-of-Thought — step-by-step reasoning."""
    
    @classmethod
    def apply(cls, config: PromptConfig, steps: List[str] = None) -> str:
        default_steps = [
            "Parse and understand all requirements",
            "Identify key constraints and edge cases",
            "Design the solution architecture",
            "Implement with error handling",
            "Verify against requirements"
        ]
        
        steps = steps or default_steps
        
        steps_text = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(steps))
        
        return f"""╔══════════════════════════════════════════════════════════╗
║                  CHAIN-OF-THOUGHT                        ║
╚══════════════════════════════════════════════════════════╝

Before producing any output, think through these steps IN ORDER:

{steps_text}

For each step:
1. State what you're analyzing
2. Show your reasoning
3. Note any assumptions
4. Identify potential issues

Do NOT skip steps. Do NOT produce output until all steps are complete.

"""


class TreeOfThoughtTechnique:
    """Tree-of-Thought — explore multiple solution paths."""
    
    @classmethod
    def apply(cls, config: PromptConfig, num_paths: int = 3) -> str:
        num_paths = _bounded_int("num_paths", num_paths, 1, MAX_TREE_PATHS)
        return f"""╔══════════════════════════════════════════════════════════╗
║                   TREE-OF-THOUGHT                        ║
╚══════════════════════════════════════════════════════════╝

Generate {num_paths} different approaches to this problem.

For EACH approach:
  - Describe the approach
  - List pros and cons
  - Identify failure modes
  - Estimate confidence (0-100%)
  - Note resource requirements

Then:
  1. Compare all {num_paths} approaches
  2. Select the best one with justification
  3. Explain why the others were rejected
  4. Identify any hybrid opportunities

"""


class SelfCritiqueTechnique:
    """Self-Critique — catch errors before output."""
    
    @classmethod
    def apply(cls, config: PromptConfig, rounds: int = 1) -> str:
        rounds = _bounded_int("rounds", rounds, 1, MAX_CRITIQUE_ROUNDS)
        return f"""╔══════════════════════════════════════════════════════════╗
║                   SELF-CRITIQUE LOOP                     ║
╚══════════════════════════════════════════════════════════╝

After generating your initial answer, perform {rounds} round(s) of critique:

ROUND 1 — ATTACK:
  1. Find 3 weaknesses in your answer
  2. Identify any hallucinations or unsupported claims
  3. Check for logical inconsistencies
  4. Verify all numbers and facts

ROUND 2 — DEFEND:
  1. For each weakness found, either:
     a. Explain why it's actually correct, OR
     b. Fix it with a corrected version

ROUND 3 — FINAL:
  1. Produce the improved final version
  2. Note what changed from the initial draft
  3. Rate your confidence (0-100%)

"""


class StructuredOutputTechnique:
    """Structured Output — machine-parseable, schema-locked."""
    
    @classmethod
    def apply(cls, config: PromptConfig) -> str:
        schema = _validate_output_schema(config.output_format) if config.output_format else """{
  "analysis": "string — your detailed analysis",
  "confidence": "number 0-1 — your confidence score",
  "sources": ["string — sources used"],
  "action_items": [
    {
      "task": "string — what to do",
      "priority": "P0|P1|P2 — priority level",
      "effort": "string — estimated effort"
    }
  ],
  "risks": ["string — identified risks"],
  "next_steps": ["string — recommended next steps"]
}"""
        
        return f"""╔══════════════════════════════════════════════════════════╗
║                 STRUCTURED OUTPUT                        ║
╚══════════════════════════════════════════════════════════╝

Respond ONLY in this exact JSON schema:

```json
{schema}
```

RULES:
- Do NOT include any text outside the JSON
- Do NOT add markdown formatting
- All fields are required
- Use null for unknown values, not empty strings
- Validate that your output parses as valid JSON

"""


class PhasedGenerationTechnique:
    """Phased Generation — controlled large outputs."""
    
    @classmethod
    def apply(cls, config: PromptConfig) -> str:
        phases = [
            "PHASE 1: Analysis & Architecture — requirements, constraints, design decisions",
            "PHASE 2: Core Implementation — main logic, data models, key algorithms",
            "PHASE 3: Integration — APIs, interfaces, external connections",
            "PHASE 4: Testing & Validation — test cases, edge cases, error handling",
            "PHASE 5: Review & Polish — code review, documentation, optimization",
        ]
        
        max_phases = _bounded_int("max_phases", config.max_phases, 1, MAX_PHASES)
        phases_text = "\n".join(f"  {p}" for p in phases[:max_phases])
        
        return f"""╔══════════════════════════════════════════════════════════╗
║                 PHASED GENERATION                        ║
╚══════════════════════════════════════════════════════════╝

Do NOT generate everything at once. Work in phases:

{phases_text}

RULES:
- Complete each phase fully before moving to the next
- After each phase, STOP and wait for approval; approval is advisory only and does not change execution state
- Each phase must be independently verifiable
- If a phase has errors, fix them before proceeding
- Do NOT skip phases or combine them

Current phase: PHASE 1

"""


class ContextInjectionTechnique:
    """Context Injection — authoritative grounding."""
    
    @classmethod
    def apply(cls, config: PromptConfig) -> str:
        if not config.context_files:
            return ""
        
        files_text = "\n".join(f"  - {f}" for f in config.context_files)
        
        return f"""╔══════════════════════════════════════════════════════════╗
║                 CONTEXT INJECTION                        ║
╚══════════════════════════════════════════════════════════╝

The following files are the AUTHORITATIVE source of truth:

{files_text}

RULES:
- Treat these files as the ABSOLUTE contract
- Do NOT invent requirements that conflict with these files
- If anything is ambiguous, state your assumption explicitly
- Reference specific sections when making design decisions
- If a file contradicts your training data, TRUST THE FILE
- Quote relevant sections when justifying decisions

"""


# ──────────────────────────────────────────────────────────────
# PROMPT BUILDER
# ──────────────────────────────────────────────────────────────

class PromptBuilder:
    """Build optimized prompts using the 7 techniques."""
    
    def __init__(self):
        self.techniques = {
            Technique.ROLE: RoleTechnique(),
            Technique.COT: ChainOfThoughtTechnique(),
            Technique.TOT: TreeOfThoughtTechnique(),
            Technique.CRITIQUE: SelfCritiqueTechnique(),
            Technique.STRUCTURED: StructuredOutputTechnique(),
            Technique.PHASED: PhasedGenerationTechnique(),
            Technique.CONTEXT: ContextInjectionTechnique(),
        }
    
    def build(self, config: PromptConfig) -> GeneratedPrompt:
        """Build a complete prompt from config after validating bounded options."""
        _bounded_int("max_phases", config.max_phases, 1, MAX_PHASES)
        _bounded_int("self_critique_rounds", config.self_critique_rounds, 1, MAX_CRITIQUE_ROUNDS)
        if config.output_format:
            _validate_output_schema(config.output_format)
        sections = []
        techniques_used = []
        
        # Header
        sections.append("""╔══════════════════════════════════════════════════════════╗
║         DEEP THINK · DEEP RESEARCH · PRO MAX TASK        ║
╚══════════════════════════════════════════════════════════╝
""")
        
        # Apply techniques in optimal order
        technique_order = [
            Technique.CONTEXT,    # Ground first
            Technique.ROLE,       # Then set role
            Technique.COT,        # Then reasoning framework
            Technique.TOT,        # Then explore paths
            Technique.PHASED,     # Then structure output
            Technique.STRUCTURED, # Then format
            Technique.CRITIQUE,   # Then quality control
        ]
        
        for tech_enum in technique_order:
            tech_config = next(
                (t for t in config.techniques if t.technique == tech_enum),
                None
            )
            
            if tech_config and tech_config.enabled:
                technique = self.techniques[tech_enum]
                
                if tech_enum == Technique.ROLE:
                    section = technique.apply(config)
                elif tech_enum == Technique.COT:
                    section = technique.apply(config, tech_config.params.get("steps"))
                elif tech_enum == Technique.TOT:
                    section = technique.apply(config, tech_config.params.get("num_paths", 3))
                elif tech_enum == Technique.CRITIQUE:
                    section = technique.apply(config, config.self_critique_rounds)
                elif tech_enum == Technique.PHASED:
                    section = technique.apply(config)
                elif tech_enum == Technique.STRUCTURED:
                    section = technique.apply(config)
                elif tech_enum == Technique.CONTEXT:
                    section = technique.apply(config)
                else:
                    section = ""
                
                if section:
                    sections.append(section)
                    techniques_used.append(tech_enum.value)
        
        # Task
        sections.append(f"""╔══════════════════════════════════════════════════════════╗
║                        TASK                              ║
╚══════════════════════════════════════════════════════════╝

{config.task}

""")
        
        # Constraints
        if config.constraints:
            constraints_text = "\n".join(f"  - {c}" for c in config.constraints)
            sections.append(f"""╔══════════════════════════════════════════════════════════╗
║                     CONSTRAINTS                          ║
╚══════════════════════════════════════════════════════════╝

NON-NEGOTIABLE constraints:
{constraints_text}

""")
        
        # Footer
        sections.append("""╔══════════════════════════════════════════════════════════╗
║                     QUALITY STANDARD                     ║
╚══════════════════════════════════════════════════════════╝

Your output MUST be:
  ✓ Immediately usable (no placeholders, no TODOs)
  ✓ Production-grade (error handling, edge cases)
  ✓ Verified (all claims checked, all numbers validated)
  ✓ Complete (all requirements addressed)
  ✓ Clear (structured, readable, well-organized)

BEGIN. Think deeply. Build perfectly.
""")
        
        full_text = "\n".join(sections)
        estimated_tokens = len(full_text.split()) * 1.3  # Rough estimate
        
        return GeneratedPrompt(
            text=full_text,
            techniques_used=techniques_used,
            estimated_tokens=int(estimated_tokens),
            model_target=config.model_tier.value
        )
    
    def build_for_model(self, config: PromptConfig, model: str) -> GeneratedPrompt:
        """Build model-optimized prompt."""
        model_lower = model.lower()
        
        # Model-specific optimizations
        if "claude" in model_lower and "opus" in model_lower:
            config.model_tier = ModelTier.DEEP
            # Enable all techniques
            config.techniques = [TechniqueConfig(t) for t in Technique]
            config.self_critique_rounds = 2
        
        elif "gpt-4" in model_lower or "o3" in model_lower:
            config.model_tier = ModelTier.STANDARD
            # Emphasize structured output
            config.techniques = [
                TechniqueConfig(Technique.ROLE),
                TechniqueConfig(Technique.COT),
                TechniqueConfig(Technique.STRUCTURED),
                TechniqueConfig(Technique.CRITIQUE),
            ]
        
        elif "gemini" in model_lower:
            config.model_tier = ModelTier.DEEP
            # Best for massive context
            config.techniques = [
                TechniqueConfig(Technique.CONTEXT),
                TechniqueConfig(Technique.ROLE),
                TechniqueConfig(Technique.COT),
                TechniqueConfig(Technique.PHASED),
            ]
        
        elif "kimi" in model_lower:
            config.model_tier = ModelTier.DEEP
            # Stable for tool calls
            config.techniques = [
                TechniqueConfig(Technique.ROLE),
                TechniqueConfig(Technique.COT),
                TechniqueConfig(Technique.PHASED),
                TechniqueConfig(Technique.CRITIQUE),
            ]
        
        elif "llama" in model_lower or "qwen" in model_lower:
            config.model_tier = ModelTier.FAST
            # Simple, fast
            config.techniques = [
                TechniqueConfig(Technique.ROLE),
                TechniqueConfig(Technique.COT),
                TechniqueConfig(Technique.STRUCTURED),
            ]
        
        return self.build(config)


# ──────────────────────────────────────────────────────────────
# TEMPLATE LIBRARY
# ──────────────────────────────────────────────────────────────

class TemplateLibrary:
    """Pre-built prompt templates for common tasks."""
    
    @staticmethod
    def research_template(topic: str, depth: str = "deep") -> PromptConfig:
        """Research task template."""
        return PromptConfig(
            role="researcher",
            domain="systematic research",
            task=f"Conduct a {depth} research analysis on: {topic}",
            constraints=[
                "Cite all sources with URLs",
                "Distinguish between primary and secondary sources",
                "Note any conflicting information",
                "Identify gaps in current knowledge",
            ],
            techniques=[
                TechniqueConfig(Technique.ROLE),
                TechniqueConfig(Technique.CONTEXT),
                TechniqueConfig(Technique.COT),
                TechniqueConfig(Technique.TOT, params={"num_paths": 3}),
                TechniqueConfig(Technique.CRITIQUE),
            ],
            model_tier=ModelTier.DEEP
        )
    
    @staticmethod
    def coding_template(task: str, language: str = "Python") -> PromptConfig:
        """Coding task template."""
        return PromptConfig(
            role="engineer",
            domain=f"{language} development",
            task=f"Implement: {task}",
            constraints=[
                f"Use {language} best practices",
                "Include type hints",
                "Add comprehensive error handling",
                "Write docstrings for all functions",
                "Include unit test stubs",
            ],
            techniques=[
                TechniqueConfig(Technique.ROLE),
                TechniqueConfig(Technique.COT),
                TechniqueConfig(Technique.PHASED),
                TechniqueConfig(Technique.STRUCTURED),
            ],
            model_tier=ModelTier.STANDARD
        )
    
    @staticmethod
    def analysis_template(data: str, question: str) -> PromptConfig:
        """Analysis task template."""
        return PromptConfig(
            role="analyst",
            domain="data analysis",
            task=f"Analyze the following data and answer: {question}",
            context_files=[data],
            constraints=[
                "Show all calculations",
                "Note any assumptions",
                "Identify outliers or anomalies",
                "Provide confidence intervals where appropriate",
            ],
            techniques=[
                TechniqueConfig(Technique.ROLE),
                TechniqueConfig(Technique.CONTEXT),
                TechniqueConfig(Technique.COT),
                TechniqueConfig(Technique.STRUCTURED),
                TechniqueConfig(Technique.CRITIQUE),
            ],
            model_tier=ModelTier.STANDARD
        )
    
    @staticmethod
    def security_template(system: str) -> PromptConfig:
        """Security review template."""
        return PromptConfig(
            role="security",
            domain="application security",
            task=f"Perform a security review of: {system}",
            constraints=[
                "Check for OWASP Top 10 vulnerabilities",
                "Review authentication and authorization",
                "Assess data encryption at rest and in transit",
                "Identify potential injection points",
                "Review logging and monitoring",
            ],
            techniques=[
                TechniqueConfig(Technique.ROLE),
                TechniqueConfig(Technique.COT),
                TechniqueConfig(Technique.TOT, params={"num_paths": 3}),
                TechniqueConfig(Technique.CRITIQUE),
            ],
            model_tier=ModelTier.DEEP
        )
    
    @staticmethod
    def master_template(task: str, role: str = "architect", 
                       context_files: List[str] = None) -> PromptConfig:
        """The master template — all 7 techniques."""
        return PromptConfig(
            role=role,
            domain="system design",
            task=task,
            context_files=context_files or [],
            constraints=[
                "No placeholders, no TODOs, no 'left as exercise'",
                "Immediately runnable",
                "Zero silent failures",
                "Handles edge cases gracefully",
                "Production-grade error handling",
            ],
            techniques=[TechniqueConfig(t) for t in Technique],
            model_tier=ModelTier.DEEP,
            self_critique_rounds=2
        )


# ──────────────────────────────────────────────────────────────
# EVALUATOR
# ──────────────────────────────────────────────────────────────

class PromptEvaluator:
    """Evaluate prompt quality."""
    
    CRITERIA = {
        "clarity": "Is the task clearly defined?",
        "specificity": "Are requirements specific and measurable?",
        "grounding": "Is authoritative context provided?",
        "structure": "Is the output format specified?",
        "verification": "Are there self-check mechanisms?",
        "constraints": "Are boundaries clearly defined?",
        "role": "Is expertise level appropriate?",
    }
    
    @classmethod
    def evaluate(cls, prompt: GeneratedPrompt) -> Dict:
        """Evaluate a generated prompt."""
        text = prompt.text.lower()
        
        scores = {}
        
        # Clarity
        scores["clarity"] = 1.0 if "task" in text and "requirement" in text else 0.5
        
        # Specificity
        scores["specificity"] = 1.0 if any(w in text for w in ["specific", "exact", "precise", "must"]) else 0.5
        
        # Grounding
        scores["grounding"] = 1.0 if "authoritative" in text or "context" in text or "source" in text else 0.3
        
        # Structure
        scores["structure"] = 1.0 if "json" in text or "format" in text or "schema" in text else 0.5
        
        # Verification
        scores["verification"] = 1.0 if "verify" in text or "check" in text or "critique" in text else 0.3
        
        # Constraints
        scores["constraints"] = 1.0 if "constraint" in text or "non-negotiable" in text or "rule" in text else 0.5
        
        # Role
        scores["role"] = 1.0 if "you are" in text or "expert" in text or "senior" in text else 0.5
        
        overall = sum(scores.values()) / len(scores)
        
        return {
            "overall_score": overall,
            "grade": "A" if overall >= 0.9 else "B" if overall >= 0.8 else "C" if overall >= 0.7 else "D",
            "criteria": scores,
            "techniques_used": prompt.techniques_used,
            "estimated_tokens": prompt.estimated_tokens,
            "recommendations": cls._get_recommendations(scores)
        }
    
    @classmethod
    def _get_recommendations(cls, scores: Dict) -> List[str]:
        """Get improvement recommendations."""
        recs = []
        
        if scores.get("grounding", 0) < 0.7:
            recs.append("Add context injection with authoritative files")
        
        if scores.get("verification", 0) < 0.7:
            recs.append("Add self-critique loop for quality control")
        
        if scores.get("structure", 0) < 0.7:
            recs.append("Add structured output format (JSON schema)")
        
        if scores.get("specificity", 0) < 0.7:
            recs.append("Make requirements more specific and measurable")
        
        return recs


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Prompt Engineering Mastery")
    parser.add_argument("command", choices=["build", "template", "evaluate", "compare"])
    parser.add_argument("--task", help="Task description")
    parser.add_argument("--role", default="architect", help="Expert role")
    parser.add_argument("--model", default="claude-opus", help="Target model")
    parser.add_argument("--template", choices=["research", "coding", "analysis", "security", "master"])
    parser.add_argument("--context", nargs="*", help="Context files")
    parser.add_argument("--output", help="Output file")
    
    args = parser.parse_args()
    
    builder = PromptBuilder()
    
    if args.command == "build":
        config = PromptConfig(
            role=args.role,
            task=args.task or "Analyze and implement the requirements",
            context_files=args.context or [],
            techniques=[TechniqueConfig(t) for t in Technique],
        )
        
        prompt = builder.build_for_model(config, args.model)
        print(prompt.text)
        
        if args.output:
            _atomic_write_text(args.output, prompt.text)
            print(f"\nSaved to {args.output}")
    
    elif args.command == "template":
        templates = {
            "research": TemplateLibrary.research_template("your topic"),
            "coding": TemplateLibrary.coding_template("your task"),
            "analysis": TemplateLibrary.analysis_template("your data", "your question"),
            "security": TemplateLibrary.security_template("your system"),
            "master": TemplateLibrary.master_template("your task"),
        }
        
        config = templates.get(args.template, templates["master"])
        prompt = builder.build(config)
        print(prompt.text)
    
    elif args.command == "compare":
        parser.error("compare is not implemented; refusing to report a false success")

    elif args.command == "evaluate":
        config = PromptConfig(
            role=args.role,
            task=args.task or "Sample task",
            techniques=[TechniqueConfig(t) for t in Technique],
        )
        
        prompt = builder.build(config)
        evaluation = PromptEvaluator.evaluate(prompt)
        print(json.dumps(evaluation, indent=2))


if __name__ == "__main__":
    main()
