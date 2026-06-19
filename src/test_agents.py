from __future__ import annotations

from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


def make_config(tmp_path: Path):
    """Student TODO: build an isolated config for tests."""
    from config import LabConfig
    from model_provider import ProviderConfig
    return LabConfig(
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
        compact_threshold_tokens=60,
        compact_keep_messages=2,
        model=ProviderConfig(provider="openai", model_name="gpt-4o-mini", temperature=0.0),
        judge_model=ProviderConfig(provider="openai", model_name="gpt-4o-mini", temperature=0.0)
    )


def test_user_markdown_read_write_edit(tmp_path: Path) -> None:
    """Student TODO: verify `User.md` can be created, updated, and edited."""
    config = make_config(tmp_path)
    from memory_store import UserProfileStore
    store = UserProfileStore(config.state_dir / "profiles")
    
    user_id = "test_user"
    
    # Test write/read
    store.write_text(user_id, "# Profile: test_user\n- location: Huế\n")
    content = store.read_text(user_id)
    assert "Huế" in content
    
    # Test edit
    changed = store.edit_text(user_id, "Huế", "Đà Nẵng")
    assert changed is True
    
    # Verify change
    new_content = store.read_text(user_id)
    assert "Đà Nẵng" in new_content
    assert "Huế" not in new_content
    assert store.file_size(user_id) > 0


def test_compact_trigger(tmp_path: Path) -> None:
    """Student TODO: verify long threads trigger compaction."""
    config = make_config(tmp_path)
    config.compact_threshold_tokens = 30
    config.compact_keep_messages = 2
    
    agent = AdvancedAgent(config, force_offline=True)
    user_id = "test_compact"
    thread_id = "thread_1"
    
    agent.reply(user_id, thread_id, "This is message 1.")
    agent.reply(user_id, thread_id, "This is message 2 which is long.")
    agent.reply(user_id, thread_id, "This is message 3 which should definitely trigger compaction.")
    
    assert agent.compaction_count(thread_id) > 0


def test_cross_session_recall(tmp_path: Path) -> None:
    """Student TODO: verify advanced remembers across sessions and baseline does not."""
    config = make_config(tmp_path)
    
    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)
    
    user_id = "user_recall"
    thread_1 = "thread_1"
    thread_2 = "thread_2"
    
    # Introduce facts
    baseline.reply(user_id, thread_1, "Chào bạn, mình tên là DũngCT.")
    advanced.reply(user_id, thread_1, "Chào bạn, mình tên là DũngCT.")
    
    # Ask recall in a new session/thread
    res_base = baseline.reply(user_id, thread_2, "Tên mình là gì?")
    res_adv = advanced.reply(user_id, thread_2, "Tên mình là gì?")
    
    # Baseline forgets
    assert "DũngCT" not in res_base["response"]
    # Advanced remembers
    assert "DũngCT" in res_adv["response"]


def test_compact_reduces_prompt_load_on_long_thread(tmp_path: Path) -> None:
    """Student TODO: compare prompt load of baseline vs advanced on a long thread."""
    config = make_config(tmp_path)
    config.compact_threshold_tokens = 60
    config.compact_keep_messages = 2
    
    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)
    
    user_id = "user_load"
    thread_id = "thread_long"
    
    messages = [
        "Tin thứ nhất: Artemis III phóng năm 2027.",
        "Tin thứ hai: X-59 bay siêu thanh Mach 1.1.",
        "Tin thứ ba: El Nino có xác suất 80% quay lại.",
        "Tin thứ tư: BC energy plan tiết kiệm điện sạch.",
        "Tin thứ năm: NASA Artemis IV hoãn đến 2028.",
        "Tin thứ sáu: Trạm vũ trụ quốc tế ISS chuẩn bị nâng cấp hệ thống pin mặt trời mới.",
        "Tin thứ bảy: Vệ tinh Copernicus đo đạc chính xác lượng phát thải khí nhà kính toàn cầu.",
        "Tin thứ tám: Siêu máy tính Aurora tại Argonne đã chính thức đi vào hoạt động toàn phần.",
        "Tin thứ chín: Dự án phục hồi rừng nhiệt đới Amazon đạt cột mốc trồng 10 triệu cây xanh.",
        "Tin thứ mười: Tàu thăm dò Voyager 1 tiếp tục gửi tín hiệu từ ngoài không gian liên sao."
    ]
    
    for m in messages:
        baseline.reply(user_id, thread_id, m)
        advanced.reply(user_id, thread_id, m)
        
    baseline_prompt = baseline.prompt_token_usage(thread_id)
    advanced_prompt = advanced.prompt_token_usage(thread_id)
    
    assert advanced.compaction_count(thread_id) > 0
    assert advanced_prompt < baseline_prompt

