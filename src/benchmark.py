from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


def load_conversations(path: Path) -> list[dict[str, Any]]:
    """Student TODO: read JSON conversations from disk."""
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def recall_points(answer: str, expected: list[str]) -> float:
    """Student TODO: return 0 / 0.5 / 1 depending on how many expected facts appear."""
    if not expected:
        return 1.0
    lower_answer = answer.lower()
    matched = sum(1 for fact in expected if fact.lower() in lower_answer)
    if matched == len(expected):
        return 1.0
    elif matched > 0:
        return 0.5
    return 0.0


def heuristic_quality(answer: str, expected: list[str]) -> float:
    """Student TODO: add a lightweight quality score for offline mode."""
    base = recall_points(answer, expected)
    if len(answer) > 0 and len(answer) < 300:
        base = min(1.0, base + 0.1)
    return base


def run_agent_benchmark(agent_name: str, agent, conversations: list[dict[str, Any]], config) -> BenchmarkRow:
    """Student TODO: evaluate one agent over many conversations.

    Pseudocode:
    1. Feed all turns to the agent.
    2. Track `agent tokens only`.
    3. Track `prompt tokens processed`.
    4. Ask recall questions in a fresh thread.
    5. Compute average recall and quality.
    6. Record memory file growth and compaction count.
    """
    total_agent_tokens = 0
    total_prompt_tokens = 0
    recall_scores = []
    quality_scores = []

    for conv in conversations:
        user_id = conv["user_id"]
        thread_id = conv["id"]

        # 1. Feed all turns to agent
        for turn in conv["turns"]:
            agent.reply(user_id, thread_id, turn)

        # 2. Track token usages
        total_agent_tokens += agent.token_usage(thread_id)
        total_prompt_tokens += agent.prompt_token_usage(thread_id)

        # 3. Ask recall questions in a fresh thread
        for idx, rq in enumerate(conv["recall_questions"]):
            recall_thread_id = f"recall-{thread_id}-{idx}"
            res = agent.reply(user_id, recall_thread_id, rq["question"])
            ans = res["response"]

            score = recall_points(ans, rq["expected_contains"])
            quality = heuristic_quality(ans, rq["expected_contains"])

            recall_scores.append(score)
            quality_scores.append(quality)

    avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    # 4. Measure memory growth
    profile_dir = config.state_dir / "profiles"
    mem_size = 0
    if profile_dir.exists():
        for f in profile_dir.glob("*.md"):
            mem_size += f.stat().st_size

    # 5. Measure compactions
    total_compactions = sum(agent.compaction_count(conv["id"]) for conv in conversations)

    return BenchmarkRow(
        agent_name=agent_name,
        agent_tokens_only=total_agent_tokens,
        prompt_tokens_processed=total_prompt_tokens,
        recall_score=avg_recall,
        response_quality=avg_quality,
        memory_growth_bytes=mem_size,
        compactions=total_compactions
    )


def format_rows(rows: list[BenchmarkRow]) -> str:
    """Student TODO: print a markdown table or tabulated output."""
    from tabulate import tabulate
    headers = [
        "Agent Name", "Agent tokens only", "Prompt tokens processed",
        "Cross-session recall", "Response quality", "Memory growth (bytes)", "Compactions"
    ]
    data = []
    for r in rows:
        data.append([
            r.agent_name,
            r.agent_tokens_only,
            r.prompt_tokens_processed,
            f"{r.recall_score:.2f}",
            f"{r.response_quality:.2f}",
            r.memory_growth_bytes,
            r.compactions
        ])
    return tabulate(data, headers=headers, tablefmt="github")


def main() -> None:
    """Student TODO: run both benchmark suites.

    Required benchmark sections:
    - Standard benchmark from `data/conversations.json`
    - Long-context stress benchmark from `data/advanced_long_context.json`

    Compare:
    - Baseline
    - Advanced

    Keep the same output columns as the solved lab:
    - Agent tokens only
    - Prompt tokens processed
    - Cross-session recall
    - Response quality
    - Memory growth (bytes)
    - Compactions
    """
    import shutil
    config = load_config(Path(__file__).resolve().parent.parent)

    std_convs = load_conversations(config.data_dir / "conversations.json")
    stress_convs = load_conversations(config.data_dir / "advanced_long_context.json")

    # Standard Benchmark
    print("=== RUNNING STANDARD BENCHMARK ===")
    
    if config.state_dir.exists():
        shutil.rmtree(config.state_dir)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    baseline_agent = BaselineAgent(config, force_offline=True)
    std_baseline_row = run_agent_benchmark("Baseline Agent", baseline_agent, std_convs, config)

    if config.state_dir.exists():
        shutil.rmtree(config.state_dir)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    advanced_agent = AdvancedAgent(config, force_offline=True)
    std_advanced_row = run_agent_benchmark("Advanced Agent", advanced_agent, std_convs, config)

    # Stress Benchmark
    print("=== RUNNING LONG-CONTEXT STRESS BENCHMARK ===")
    
    if config.state_dir.exists():
        shutil.rmtree(config.state_dir)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    baseline_agent_stress = BaselineAgent(config, force_offline=True)
    stress_baseline_row = run_agent_benchmark("Baseline Agent", baseline_agent_stress, stress_convs, config)

    if config.state_dir.exists():
        shutil.rmtree(config.state_dir)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    advanced_agent_stress = AdvancedAgent(config, force_offline=True)
    stress_advanced_row = run_agent_benchmark("Advanced Agent", advanced_agent_stress, stress_convs, config)

    # Results
    print("\nStandard Benchmark Results:")
    print(format_rows([std_baseline_row, std_advanced_row]))

    print("\nLong-Context Stress Benchmark Results:")
    print(format_rows([stress_baseline_row, stress_advanced_row]))


if __name__ == "__main__":
    main()

