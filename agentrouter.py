#!/usr/bin/env python3
"""
AgentRouter — intelligent task routing for multi-agent systems.

Classify incoming tasks and route them to the right agent/model based on:
  • Task type (classification via keyword heuristics)
  • Capability match (works with AgentCard manifests)
  • Cost budget (skip agents that exceed max cost)
  • Trust level (only route to verified+ agents)

No LLM needed for routing — deterministic heuristics.

Pure Python standard library. Zero dependencies.

Domains: agent orchestration · multi-agent systems · task dispatch.
"""
import argparse, json, sys


TASK_PATTERNS = {
    "summarize": ["summary", "summarize", "tldr", "recap", "brief"],
    "search": ["search", "find", "lookup", "query", "what is", "who is", "where is"],
    "code": ["code", "write", "function", "debug", "fix", "implement", "refactor"],
    "analyze": ["analyze", "analysis", "compare", "evaluate", "assess", "review"],
    "translate": ["translate", "translation", "convert to"],
    "generate": ["generate", "create", "make", "build", "design", "draft"],
}


def classify(task_text):
    text = task_text.lower()
    scores = {}
    for task_type, keywords in TASK_PATTERNS.items():
        scores[task_type] = sum(1 for kw in keywords if kw in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def route(task, agents, max_cost=None, min_trust=None):
    task_type = classify(task)
    candidates = []

    for agent in agents:
        caps = [c["name"] for c in agent.get("capabilities", [])]
        trust = agent.get("trust", "unverified")
        trust_ranks = {"unverified": 0, "self-attested": 1, "verified": 2, "certified": 3}

        # Capability match
        if task_type not in caps and "general" not in caps and "*" not in caps:
            continue

        # Trust gate
        if min_trust and trust_ranks.get(trust, 0) < trust_ranks.get(min_trust, 0):
            continue

        # Cost gate
        agent_cost = 0
        for c in agent.get("capabilities", []):
            if c["name"] == task_type or c["name"] == "general":
                agent_cost = c.get("cost_usd", 0)
                break
        if max_cost is not None and agent_cost > max_cost:
            continue

        candidates.append({
            "agent": agent["name"],
            "id": agent.get("id", agent["name"]),
            "task_type": task_type,
            "cost": agent_cost,
            "trust": trust,
            "caps_matched": task_type in caps,
        })

    # Sort: exact match first, then cheapest
    candidates.sort(key=lambda c: (not c["caps_matched"], c["cost"]))
    return {"task": task[:80], "task_type": task_type, "candidates": candidates}


def cmd(args):
    task = args.task or sys.stdin.read().strip()
    agents = json.load(open(args.agents, encoding="utf-8"))
    result = route(task, agents, args.max_cost, args.min_trust)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"Task: {result['task']}")
        print(f"Classified as: {result['task_type']}")
        print(f"Candidates: {len(result['candidates'])}")
        for c in result["candidates"]:
            star = "⭐" if c["caps_matched"] else "  "
            print(f"  {star} {c['agent']} (trust={c['trust']}, ${c['cost']})")
    return 0


def main():
    p = argparse.ArgumentParser(prog="agentrouter", description=__doc__)
    p.add_argument("--task", help="task description")
    p.add_argument("--agents", required=True, help="JSON array of agent cards")
    p.add_argument("--max-cost", type=float)
    p.add_argument("--min-trust", choices=["unverified", "self-attested", "verified", "certified"])
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=cmd)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
