"""Interactive REPL with explicit, exact-payload tool approval."""
from __future__ import annotations

import json
import sys
from typing import Any

from personal_agent.agent.planner import plan


def _approve_in_terminal(tool_name: str, args: dict[str, Any]) -> bool:
    print("\nTool proposal — review the exact payload before approving:")
    print(json.dumps({"tool": tool_name, "args": args}, indent=2, ensure_ascii=False, sort_keys=True))
    try:
        answer = input("Execute this exact tool call? Type 'yes' to approve [default: no]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer == "yes"


def main() -> None:
    print("Personal Agent (Perplexity bridge) — type 'exit' or Ctrl-D to quit.")
    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not user_input:
            continue

        result = plan(user_input, approve_tool=_approve_in_terminal)
        if result["type"] == "tool":
            print("[Tool]", result["tool"], "=>")
            print(json.dumps(result["result"], indent=2, ensure_ascii=False))
        else:
            if result.get("warning"):
                print("[Warning]", result["warning"])
            print(result.get("result", result))


if __name__ == "__main__":
    sys.path.append(str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    main()
