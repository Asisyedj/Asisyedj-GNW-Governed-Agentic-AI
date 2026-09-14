---
name: prompt-engineering-mastery
description: Use when asked to write, improve, or optimize a prompt, design a system prompt, apply chain-of-thought / tree-of-thought / ReAct / self-consistency techniques, or engineer prompts for a specific model. Trigger phrases: 'improve this prompt', 'write a prompt for', 'prompt engineering', 'system prompt', 'make the model reason step by step'. Combines 7 techniques: role assignment, CoT, ToT, self-critique, structured output, phased generation, context injection.
---

# Prompt Engineering Mastery System

A prompt engineering system combining 7 techniques into a unified framework.

## The 7 Techniques

| Technique | Purpose | Evidence / Cost |
|---|---|---|---|
| Role Assignment | Activate domain expertise | Qualitative / Low |
| Chain-of-Thought | Step-by-step reasoning | Qualitative / Low |
| Tree-of-Thought | Explore multiple paths | Qualitative / High |
| Self-Critique | Catch hallucinations | Qualitative / Medium |
| Structured Output | Machine-parseable | Reliability / Low |
| Phased Generation | Large output control | Quality / Medium |
| Context Injection | Authoritative grounding | Grounding / Low |

## Architecture

```
prompt_mastery/
├── techniques/
│   ├── role.py              # Role assignment
│   ├── cot.py               # Chain-of-thought
│   ├── tot.py               # Tree-of-thought
│   ├── critique.py          # Self-critique loop
│   ├── structured.py        # Structured output
│   ├── phased.py            # Phased generation
│   └── context.py           # Context injection
├── optimizer/
│   ├── selector.py          # Technique selector
│   ├── combiner.py          # Technique combiner
│   ├── evaluator.py         # Output evaluator
│   └── model_specific.py    # Model-specific configs
├── templates/
│   ├── master.py            # Master template
│   ├── research.py          # Research template
│   ├── coding.py            # Coding template
│   ├── analysis.py          # Analysis template
│   └── creative.py          # Creative template
└── cli.py                   # build | optimize | evaluate | compare
```

## Model-Specific Optimizations

| Model family | Best Technique | Context characteristic | Special |
|---|---|---|---|
| Claude Opus | Phased + CoT | Extended | Extended Thinking |
| GPT-4o | Structured + Critique | Long | JSON Mode |
| Gemini 2.5 | Deep Research + Context | Long | Large documents |
| Kimi-K2 | Phased + Proofread | Long | Tool use |
| Local (Llama-3) | Simple CoT + Structured | Compact | Fast tier |
