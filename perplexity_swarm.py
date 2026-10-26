"""
GNW Perplexity Bridge Thinking Swarm Orchestrator
=================================================
A high-performance multi-model Swarm powered exclusively by the GNW Perplexity Bridge.

Swarm Fleet:
  1. Claude Sonnet 5.5 Thinking    (anthropic/claude-sonnet-5.5-thinking) - Chief Architect & Synthesizer
  2. GPT-6.1 Sol Thinking         (openai/gpt-6.1-sol-thinking)          - Logic & Algorithmic Strategist
  3. Grok 4.7 Thinking            (x-ai/grok-4.7-thinking)               - Adversarial Red-Teamer & Auditor
  4. Gemini 3.8 Flash Thinking    (google/gemini-3.8-flash-thinking)     - High-Velocity Explorer & Connector
  5. Kimi K3 Thinking             (moonshot/kimi-k3-thinking)            - Long-Horizon CoT & Verifier
  6. GLM 5.3                      (z-ai/glm-5.3)                         - Polymath Integrator & Reasoner

Features:
  - Max thinking budget instructions enforced per agent
  - Parallel execution via ThreadPoolExecutor
  - Consensus Council Mode (parallel generation + master synthesis)
  - Adversarial Debate Mode (thesis -> red-team critique -> defense/synthesis)
  - Pipeline Mode (staged progressive reasoning)
  - Complete run reports in Markdown and JSON
"""

import os
import sys
import json
import time
import datetime
from pathlib import Path

# Ensure directory is in sys.path for gnw_secrets
SWARM_DIR = Path(__file__).resolve().parent
if str(SWARM_DIR) not in sys.path:
    sys.path.insert(0, str(SWARM_DIR))

from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional

# Bridge configuration
BRIDGE_URL = os.environ.get("PERPLEXITY_BRIDGE_URL", "http://127.0.0.1:8000")

def _get_api_key() -> str:
    """Retrieve the DPAPI sealed bridge key or fallback to environment."""
    if "PERPLEXITY_BRIDGE_KEY" in os.environ:
        return os.environ["PERPLEXITY_BRIDGE_KEY"]
    try:
        from gnw_secrets import get_bridge_key
        return get_bridge_key()
    except Exception as exc:
        raise RuntimeError(f"Failed to load bridge key: {exc}")

# Define the Flagship Swarm Agents
SWARM_MEMBERS = {
    "claude_sonnet_55": {
        "name": "Claude Sonnet 5.5 Thinking",
        "model_id": "anthropic/claude-sonnet-5.5-thinking",
        "role": "Chief Architect & Reasoning Synthesizer",
        "max_thinking_prompt": (
            "You are Claude Sonnet 5.5 operating at MAXIMUM COGNITIVE & REASONING BUDGET. "
            "Engage in deep, multi-step chain-of-thought. Deconstruct the problem from first principles, "
            "evaluate critical trade-offs, question latent assumptions, synthesize divergent viewpoints, "
            "and formulate mathematically sound, high-leverage architectural conclusions."
        ),
    },
    "gpt_61_sol": {
        "name": "GPT-6.1 Sol Thinking",
        "model_id": "openai/gpt-6.1-sol-thinking",
        "role": "Logic, Algorithmic & Strategic Specialist",
        "max_thinking_prompt": (
            "You are GPT-6.1 Sol operating at MAXIMUM REASONING DEPTH. Engage in exhaustive "
            "chain-of-thought reasoning. Provide rigorous step-by-step logic, formal verification, "
            "algorithmic precision, and optimize for zero error tolerance and maximal computational leverage."
        ),
    },
    "grok_47": {
        "name": "Grok 4.7 Thinking",
        "model_id": "x-ai/grok-4.7-thinking",
        "role": "Adversarial Red-Teamer & Critical Auditor",
        "max_thinking_prompt": (
            "You are Grok 4.7 operating at MAXIMUM CRITICAL THINKING LEVEL. Your mandate is relentless "
            "adversarial stress-testing. Expose edge cases, hidden failure modes, vulnerabilities, and "
            "cognitive blindspots. Speak with blunt, rigorous intellectual honesty."
        ),
    },
    "gemini_38_flash": {
        "name": "Gemini 3.8 Flash Thinking",
        "model_id": "google/gemini-3.8-flash-thinking",
        "role": "High-Velocity Explorer & Multi-Domain Connector",
        "max_thinking_prompt": (
            "You are Gemini 3.8 Flash operating in MAXIMUM THINKING MODE. Rapidly cross-reference "
            "multidisciplinary domains, map the full problem topography, discover non-obvious connections, "
            "and establish expansive architectural solutions with high velocity and clarity."
        ),
    },
    "kimi_k3": {
        "name": "Kimi K3 Thinking",
        "model_id": "moonshot/kimi-k3-thinking",
        "role": "Long-Horizon CoT & Multi-Step Verifier",
        "max_thinking_prompt": (
            "You are Kimi K3 operating with MAXIMUM REASONING TRACE. Exhaustively trace state transitions, "
            "verify causal dependency graphs, evaluate long-horizon second- and third-order effects, and audit "
            "intricate execution chains without skipping intermediate derivations."
        ),
    },
    "glm_53": {
        "name": "GLM 5.3",
        "model_id": "z-ai/glm-5.3",
        "role": "Polymath Integrator & Poly-Perspective Reasoner",
        "max_thinking_prompt": (
            "You are GLM 5.3 operating at PEAK COGNITIVE CAPACITY. Analyze the query through multiple "
            "epistemic and technical lenses. Synthesize comprehensive, holistic paradigms that bridge "
            "theoretical elegance with real-world, high-performance operational execution."
        ),
    },
}

class PerplexitySwarm:
    def __init__(self, bridge_url: str = BRIDGE_URL, timeout: int = 180):
        self.bridge_url = bridge_url
        self.timeout = timeout
        self.api_key = _get_api_key()
        self.runs_dir = Path("D:/GNW/perplexity-browser-api/swarm_runs")
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _call_model(self, model_id: str, prompt: str, system_message: str) -> Dict[str, Any]:
        """Send a single request to the Perplexity Bridge."""
        start_time = time.time()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.bridge_url}/v1/chat/completions",
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                duration = time.time() - start_time
                choices = result.get("choices", [])
                content = choices[0].get("message", {}).get("content", "") if choices else ""
                return {
                    "success": True,
                    "content": content,
                    "duration": round(duration, 2),
                    "model": model_id,
                }
        except Exception as exc:
            duration = time.time() - start_time
            return {
                "success": False,
                "error": str(exc),
                "duration": round(duration, 2),
                "model": model_id,
            }

    def ask_agent(self, agent_key: str, prompt: str, extra_instruction: str = "") -> Dict[str, Any]:
        """Query a single swarm member with its dedicated max-thinking system prompt."""
        if agent_key not in SWARM_MEMBERS:
            raise ValueError(f"Unknown agent key: {agent_key}")
        agent = SWARM_MEMBERS[agent_key]
        sys_msg = agent["max_thinking_prompt"]
        if extra_instruction:
            sys_msg += f"\n\nSpecial Swarm Directive: {extra_instruction}"
        
        res = self._call_model(agent["model_id"], prompt, sys_msg)
        res["agent_key"] = agent_key
        res["name"] = agent["name"]
        res["role"] = agent["role"]
        return res

    def run_council(self, prompt: str, max_workers: int = 6) -> Dict[str, Any]:
        """
        Mode 1: Council Consensus Swarm
        Queries all 6 models in parallel with max thinking.
        Then uses Claude Sonnet 5.5 Thinking to synthesize the Master Consensus.
        """
        print(f"\n[SWARM] Launching Council Consensus for {len(SWARM_MEMBERS)} Thinking Models...")
        start_all = time.time()
        results = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_agent = {
                executor.submit(self.ask_agent, key, prompt): key
                for key in SWARM_MEMBERS
            }
            for future in as_completed(future_to_agent):
                key = future_to_agent[future]
                try:
                    res = future.result()
                    results[key] = res
                    status = "OK" if res.get("success") else "FAILED"
                    print(f"  -> [{status}] {SWARM_MEMBERS[key]['name']} ({res.get('duration')}s)")
                except Exception as exc:
                    results[key] = {"success": False, "error": str(exc)}
                    print(f"  -> [ERROR] {SWARM_MEMBERS[key]['name']}: {exc}")

        # Synthesis Phase
        print("[SWARM] Synthesizing consensus via Claude Sonnet 5.5 Thinking...")
        dossier = "\n\n".join([
            f"=== {r.get('name')} ({r.get('role')}) ===\n{r.get('content')}"
            for r in results.values() if r.get("success")
        ])

        synthesis_prompt = (
            f"User Query:\n{prompt}\n\n"
            f"Below are the independent deep-reasoning analyses from the 6 flagship thinking models "
            f"(Claude Sonnet 5.5, GPT-6.1 Sol, Grok 4.7, Gemini 3.8 Flash, Kimi K3, GLM 5.3):\n\n"
            f"{dossier}\n\n"
            f"As Chief Architect and Supreme Synthesizer, produce the definitive Master Consensus:\n"
            f"1. Core Agreement Points (Unanimous Truths)\n"
            f"2. Key Divergences / Controversies & How to Resolve Them\n"
            f"3. Identified Edge Cases & Failure Modes (Red-Team insights)\n"
            f"4. The Unified, Authoritative Solution & Final Implementation Plan"
        )

        synthesis_res = self.ask_agent(
            "claude_sonnet_55",
            synthesis_prompt,
            extra_instruction="You are producing the official Swarm Council Consensus. Be exhaustive, mathematically precise, and decisive.",
        )

        total_time = round(time.time() - start_all, 2)
        run_record = {
            "mode": "council_consensus",
            "timestamp": datetime.datetime.now().isoformat(),
            "prompt": prompt,
            "total_duration_sec": total_time,
            "agent_responses": results,
            "master_consensus": synthesis_res.get("content", ""),
            "synthesis_duration_sec": synthesis_res.get("duration", 0),
        }
        self._save_run("council", run_record)
        return run_record

    def run_debate(self, prompt: str) -> Dict[str, Any]:
        """
        Mode 2: Adversarial Debate Swarm
        Round 1: Initial proposals from GPT-6.1 Sol and Gemini 3.8 Flash.
        Round 2: Critical stress-test & counter-arguments by Grok 4.7 & Kimi K3.
        Round 3: Adjudication and final consensus by Claude Sonnet 5.5 & GLM 5.3.
        """
        print(f"\n[SWARM] Launching 3-Round Adversarial Debate...")
        start_all = time.time()

        # Round 1: Thesis / Solutions
        print("[Round 1] Gathering Initial Theses (GPT-6.1 Sol & Gemini 3.8 Flash)...")
        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(self.ask_agent, "gpt_61_sol", prompt)
            f2 = executor.submit(self.ask_agent, "gemini_38_flash", prompt)
            r1_gpt = f1.result()
            r1_gemini = f2.result()

        # Round 2: Adversarial Critique
        print("[Round 2] Stress-Testing Theses (Grok 4.7 & Kimi K3)...")
        critique_prompt = (
            f"Original Query:\n{prompt}\n\n"
            f"Proposal A (GPT-6.1 Sol):\n{r1_gpt.get('content')}\n\n"
            f"Proposal B (Gemini 3.8 Flash):\n{r1_gemini.get('content')}\n\n"
            f"Critique and stress-test both proposals relentlessly. Expose flaws, edge cases, "
            f"hidden assumptions, and logical fallacies."
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            f3 = executor.submit(self.ask_agent, "grok_47", critique_prompt)
            f4 = executor.submit(self.ask_agent, "kimi_k3", critique_prompt)
            r2_grok = f3.result()
            r2_kimi = f4.result()

        # Round 3: Synthesis & Verdict
        print("[Round 3] Adjudication & Supreme Verdict (Claude Sonnet 5.5 & GLM 5.3)...")
        verdict_prompt = (
            f"Original Query:\n{prompt}\n\n"
            f"Proposals:\n"
            f"- GPT-6.1 Sol: {r1_gpt.get('content')}\n"
            f"- Gemini 3.8 Flash: {r1_gemini.get('content')}\n\n"
            f"Critiques:\n"
            f"- Grok 4.7: {r2_grok.get('content')}\n"
            f"- Kimi K3: {r2_kimi.get('content')}\n\n"
            f"Deliver the Final Verdict and Unified Robust Plan after taking all critiques into account."
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            f5 = executor.submit(self.ask_agent, "claude_sonnet_55", verdict_prompt)
            f6 = executor.submit(self.ask_agent, "glm_53", verdict_prompt)
            r3_claude = f5.result()
            r3_glm = f6.result()

        total_time = round(time.time() - start_all, 2)
        run_record = {
            "mode": "adversarial_debate",
            "timestamp": datetime.datetime.now().isoformat(),
            "prompt": prompt,
            "total_duration_sec": total_time,
            "round_1_theses": {"gpt_61_sol": r1_gpt, "gemini_38_flash": r1_gemini},
            "round_2_critiques": {"grok_47": r2_grok, "kimi_k3": r2_kimi},
            "round_3_verdicts": {"claude_sonnet_55": r3_claude, "glm_53": r3_glm},
        }
        self._save_run("debate", run_record)
        return run_record

    def _save_run(self, prefix: str, record: Dict[str, Any]):
        """Save JSON and Markdown audit logs of the swarm execution."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = self.runs_dir / f"{prefix}_{ts}.json"
        md_path = self.runs_dir / f"{prefix}_{ts}.md"

        json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

        # Generate Markdown view
        md_lines = [
            f"# Swarm Run Report: {record.get('mode', prefix).upper()}",
            f"- **Timestamp**: `{record.get('timestamp')}`",
            f"- **Duration**: `{record.get('total_duration_sec')}s`",
            f"- **Bridge Target**: `{self.bridge_url}`",
            f"\n## Prompt\n> {record.get('prompt')}\n",
        ]

        if "master_consensus" in record:
            md_lines.append(f"## Master Consensus (Synthesized by Claude Sonnet 5.5 Thinking)\n")
            md_lines.append(record["master_consensus"])
            md_lines.append("\n---\n## Individual Member Analyses\n")
            for k, resp in record.get("agent_responses", {}).items():
                md_lines.append(f"### {resp.get('name')} ({resp.get('role')}) - {resp.get('duration')}s\n")
                if resp.get("success"):
                    md_lines.append(resp.get("content", ""))
                else:
                    md_lines.append(f"**Error**: {resp.get('error')}")
                md_lines.append("\n---\n")

        elif "round_1_theses" in record:
            md_lines.append("## Round 1: Theses\n")
            for k, resp in record["round_1_theses"].items():
                md_lines.append(f"### {resp.get('name')}\n{resp.get('content')}\n")
            md_lines.append("## Round 2: Adversarial Critiques\n")
            for k, resp in record["round_2_critiques"].items():
                md_lines.append(f"### {resp.get('name')}\n{resp.get('content')}\n")
            md_lines.append("## Round 3: Final Verdicts\n")
            for k, resp in record["round_3_verdicts"].items():
                md_lines.append(f"### {resp.get('name')}\n{resp.get('content')}\n")

        md_path.write_text("\n".join(md_lines), encoding="utf-8")
        print(f"[SWARM] Run saved to {json_path.name} and {md_path.name}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GNW Perplexity Bridge 6-Model Thinking Swarm")
    parser.add_argument("--mode", choices=["council", "debate"], default="council", help="Swarm execution mode")
    parser.add_argument("--prompt", required=True, help="The prompt/task for the swarm")
    args = parser.parse_args()

    swarm = PerplexitySwarm()
    if args.mode == "council":
        res = swarm.run_council(args.prompt)
        print("\n" + "="*80)
        print("MASTER SWARM CONSENSUS:")
        print("="*80)
        print(res.get("master_consensus"))
    elif args.mode == "debate":
        res = swarm.run_debate(args.prompt)
        print("\n" + "="*80)
        print("DEBATE FINAL VERDICT (Claude Sonnet 5.5 Thinking):")
        print("="*80)
        claude_verdict = res.get("round_3_verdicts", {}).get("claude_sonnet_55", {}).get("content", "")
        print(claude_verdict)

if __name__ == "__main__":
    main()
