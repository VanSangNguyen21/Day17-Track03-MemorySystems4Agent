from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from model_provider import ProviderConfig


@dataclass
class LabConfig:
    """Student TODO: define the shared configuration for the lab.

    Hints:
    - Keep paths for the repo root, dataset directory, and state directory.
    - Add compact-memory settings such as threshold and number of messages to keep.
    - Add provider settings for `openai`, `custom`, `gemini`, `anthropic`, `ollama`, and `openrouter`.
    """

    base_dir: Path
    data_dir: Path
    state_dir: Path
    compact_threshold_tokens: int
    compact_keep_messages: int
    model: ProviderConfig
    judge_model: ProviderConfig


def load_config(base_dir: Path | None = None) -> LabConfig:
    import os
    from dotenv import load_dotenv

    root = (base_dir or Path(__file__).resolve().parent.parent).resolve()

    # Load from .env if present
    env_path = root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    # Ensure state directory exists
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # Load provider details
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    # Adapt if custom/NVIDIA base URL is used
    if base_url and provider == "openai":
        provider = "custom"

    model_config = ProviderConfig(
        provider=provider,
        model_name=model_name,
        temperature=0.0,
        api_key=api_key,
        base_url=base_url
    )

    judge_config = ProviderConfig(
        provider=provider,
        model_name=model_name,
        temperature=0.0,
        api_key=api_key,
        base_url=base_url
    )

    compact_threshold = int(os.getenv("COMPACT_THRESHOLD_TOKENS", "1000"))
    compact_keep = int(os.getenv("COMPACT_KEEP_MESSAGES", "6"))

    return LabConfig(
        base_dir=root,
        data_dir=root / "data",
        state_dir=state_dir,
        compact_threshold_tokens=compact_threshold,
        compact_keep_messages=compact_keep,
        model=model_config,
        judge_model=judge_config
    )

