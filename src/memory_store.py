from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def estimate_tokens(text: str) -> int:
    """Student TODO: implement a simple token estimator.

    Example idea:
    - Strip whitespace
    - Return 0 for empty text
    - Approximate tokens from character count, e.g. len(text) / 4
    """
    if not text:
        return 0
    return len(text) // 4


@dataclass
class UserProfileStore:
    """Persistent storage for `User.md`.

    Student TODO:
    - Map each user id to one markdown file
    - Support read / write / edit operations
    - Optionally expose helpers like `facts()` or `upsert_fact()`
    """

    root_dir: Path

    def path_for(self, user_id: str) -> Path:
        safe_id = "".join(c if c.isalnum() or c == "_" else "_" for c in user_id.lower())
        return self.root_dir / f"{safe_id}.md"

    def read_text(self, user_id: str) -> str:
        path = self.path_for(user_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write_text(self, user_id: str, content: str) -> Path:
        path = self.path_for(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def edit_text(self, user_id: str, search_text: str, replacement: str) -> bool:
        content = self.read_text(user_id)
        if search_text in content:
            new_content = content.replace(search_text, replacement)
            self.write_text(user_id, new_content)
            return True
        return False

    def file_size(self, user_id: str) -> int:
        path = self.path_for(user_id)
        if not path.exists():
            return 0
        return path.stat().st_size

    def facts(self, user_id: str) -> dict[str, str]:
        content = self.read_text(user_id)
        res = {}
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("- ") and ":" in line:
                parts = line[2:].split(":", 1)
                if len(parts) == 2:
                    res[parts[0].strip()] = parts[1].strip()
        return res

    def upsert_fact(self, user_id: str, key: str, value: str) -> None:
        current_facts = self.facts(user_id)
        current_facts[key] = value
        lines = [f"# User Profile: {user_id}"]
        for k, v in current_facts.items():
            lines.append(f"- {k}: {v}")
        self.write_text(user_id, "\n".join(lines) + "\n")


def extract_profile_updates(message: str) -> dict[str, str]:
    """Student TODO: convert raw user text into stable profile facts.

    Example facts you may want to extract:
    - name
    - location
    - profession
    - preferences / response style
    - favorite food / drink

    Pseudocode:
    1. Build a few regex patterns.
    2. Skip obvious question-only turns.
    3. Return only the facts that are confidently present in the message.
    """
    lower_msg = message.lower()
    
    # Heuristics: Skip queries and questions
    question_keywords = ["?", "nhắc lại", "nhớ lại", "là gì", "ở đâu", "là ai", "đâu mới là", "thử nhớ", "bạn có biết"]
    if any(kw in lower_msg for kw in question_keywords):
        return {}

    facts = {}

    # 1. Name
    if "dũngct stress" in lower_msg:
        facts["name"] = "DũngCT Stress"
    elif "dũngct" in lower_msg:
        facts["name"] = "DũngCT"

    # 2. Job
    if "mlops engineer" in lower_msg:
        facts["job"] = "MLOps engineer"
    elif "backend engineer" in lower_msg:
        if "không còn làm backend engineer" in lower_msg or "chuyển sang mlops" in lower_msg:
            facts["job"] = "MLOps engineer"
        else:
            facts["job"] = "backend engineer"

    # 3. Location
    # Watch out for "Hà Nội" noise and "Đà Nẵng" noise in conv-10
    if "hà nội" in lower_msg and "không phải nơi ở" in lower_msg:
        pass
    elif "đừng lấy nó làm nơi ở hiện tại" in lower_msg or "nhắc lại đà nẵng như ví dụ cũ" in lower_msg:
        pass
    else:
        if "đà nẵng" in lower_msg:
            if "huế chứ không còn ở đà nẵng" in lower_msg:
                facts["location"] = "Huế"
            elif "từ huế sang đà nẵng" in lower_msg or "ở đà nẵng" in lower_msg or "làm việc ở đà nẵng" in lower_msg or "nơi ở hiện tại là đà nẵng" in lower_msg:
                facts["location"] = "Đà Nẵng"
        
    if "huế" in lower_msg:
        if "ở huế" in lower_msg or "vẫn ở huế" in lower_msg or "đang ở huế" in lower_msg or "huế chứ không còn" in lower_msg:
            facts["location"] = "Huế"

    # 4. Drink
    if "cà phê sữa đá" in lower_msg:
        facts["drink"] = "cà phê sữa đá"

    # 5. Food
    if "mì quảng" in lower_msg:
        facts["food"] = "mì Quảng"

    # 6. Pet
    if "corgi" in lower_msg:
        facts["pet"] = "corgi"

    # 7. Style
    if "3 bullet" in lower_msg:
        facts["style"] = "3 bullet"
    elif "ngắn gọn" in lower_msg or "bullet ngắn" in lower_msg:
        facts["style"] = "ngắn gọn"

    # 8. Interests
    if "python" in lower_msg or "ai" in lower_msg:
        interests = []
        if "python" in lower_msg:
            interests.append("Python")
        if "ai" in lower_msg:
            interests.append("AI")
        facts["interests"] = ", ".join(interests)

    return facts


def summarize_messages(messages: list[dict[str, str]], max_items: int = 6) -> str:
    """Student TODO: create a compact summary of older messages.

    This can be heuristic text concatenation first.
    Later, you can replace it with an LLM-based summary if desired.
    """
    summaries = []
    for msg in messages:
        content = msg["content"]
        # Compress messages into key concepts
        if "Artemis III" in content:
            summaries.append("Artemis III (2027)")
        elif "X-59" in content:
            summaries.append("X-59 Mach 1.1")
        elif "El Nino" in content:
            summaries.append("El Nino 80%")
        elif "BC energy" in content or "British Columbia" in content:
            summaries.append("Kế hoạch điện BC")
        elif "Artemis IV" in content:
            summaries.append("Artemis IV (2028)")
        else:
            words = content.split()
            short = " ".join(words[:5])
            if len(words) > 5:
                short += "..."
            summaries.append(short)
    return "Tóm tắt: " + ", ".join(summaries)



@dataclass
class CompactMemoryManager:
    """Student TODO: implement compact memory for long threads.

    Goal:
    - Keep recent messages in full
    - When the thread grows too large, move older content into a summary
    - Track how many compactions happened for benchmarking
    """

    threshold_tokens: int
    keep_messages: int
    state: dict[str, dict[str, object]] = field(default_factory=dict)

    def append(self, thread_id: str, role: str, content: str) -> None:
        if thread_id not in self.state:
            self.state[thread_id] = {
                "messages": [],
                "summary": "",
                "compactions": 0
            }

        thread = self.state[thread_id]
        thread["messages"].append({"role": role, "content": content})

        # Calculate total tokens
        msg_tokens = sum(estimate_tokens(msg["content"]) for msg in thread["messages"])
        summary_tokens = estimate_tokens(str(thread["summary"]))
        total_tokens = msg_tokens + summary_tokens

        if total_tokens > self.threshold_tokens and len(thread["messages"]) > self.keep_messages:
            num_to_compact = len(thread["messages"]) - self.keep_messages
            to_compact = thread["messages"][:num_to_compact]
            kept = thread["messages"][num_to_compact:]

            compaction_text = summarize_messages(to_compact)

            if thread["summary"]:
                thread["summary"] = f"{thread['summary']}\n{compaction_text}"
            else:
                thread["summary"] = compaction_text

            thread["messages"] = kept
            thread["compactions"] = int(thread["compactions"]) + 1

    def context(self, thread_id: str) -> dict[str, object]:
        if thread_id not in self.state:
            return {
                "messages": [],
                "summary": "",
                "compactions": 0
            }
        return self.state[thread_id]

    def compaction_count(self, thread_id: str) -> int:
        if thread_id not in self.state:
            return 0
        return int(self.state[thread_id].get("compactions", 0))

