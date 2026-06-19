from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates
from model_provider import build_chat_model


@dataclass
class AgentContext:
    user_id: str
    memory_path: str


class AdvancedAgent:

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.profile_store = UserProfileStore(self.config.state_dir / "profiles")
        self.compact_memory = CompactMemoryManager(
            threshold_tokens=self.config.compact_threshold_tokens,
            keep_messages=self.config.compact_keep_messages,
        )
        self.thread_tokens: dict[str, int] = {}
        self.thread_prompt_tokens: dict[str, int] = {}

        # Initialize real LangChain agent if possible
        self.langchain_agent = None
        if not self.force_offline:
            self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: route between offline mode and live mode."""
        if self.force_offline or self.langchain_agent is None:
            return self._reply_offline(user_id, thread_id, message)

        try:
            # 1. Extract and update profile facts
            updates = extract_profile_updates(message)
            for key, val in updates.items():
                self.profile_store.upsert_fact(user_id, key, val)

            # 2. Append incoming message to compact memory
            self.compact_memory.append(thread_id, "user", message)

            # 3. Build context for the live LLM call
            profile = self.profile_store.read_text(user_id)
            ctx = self.compact_memory.context(thread_id)
            summary = ctx.get("summary", "")
            messages = ctx.get("messages", [])

            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

            system_prompt = (
                "Bạn là một AI assistant hữu ích.\n"
                f"Thông tin người dùng thu thập được (User.md):\n{profile}\n\n"
            )
            if summary:
                system_prompt += f"Tóm tắt phần hội thoại trước đó (Compact Memory):\n{summary}\n\n"

            langchain_messages = [SystemMessage(content=system_prompt)]

            # Convert message history (excluding the last one which is current user message)
            for msg in messages[:-1]:
                if msg["role"] == "user":
                    langchain_messages.append(HumanMessage(content=msg["content"]))
                else:
                    langchain_messages.append(AIMessage(content=msg["content"]))

            # Add current user message
            langchain_messages.append(HumanMessage(content=message))

            # 4. Invoke LLM
            response = self.langchain_agent.invoke(langchain_messages)
            response_text = response.content

            # 5. Save assistant reply to compact memory
            self.compact_memory.append(thread_id, "assistant", response_text)

            # 6. Estimate prompt and reply tokens
            prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
            reply_tokens = estimate_tokens(response_text)

            if thread_id not in self.thread_tokens:
                self.thread_tokens[thread_id] = 0
                self.thread_prompt_tokens[thread_id] = 0

            self.thread_tokens[thread_id] += reply_tokens
            self.thread_prompt_tokens[thread_id] += prompt_tokens

            return {
                "response": response_text,
                "tokens": reply_tokens,
                "prompt_tokens": prompt_tokens
            }
        except Exception:
            return self._reply_offline(user_id, thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        return self.thread_tokens.get(thread_id, 0)

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.thread_prompt_tokens.get(thread_id, 0)

    def memory_file_size(self, user_id: str) -> int:
        return self.profile_store.file_size(user_id)

    def compaction_count(self, thread_id: str) -> int:
        return self.compact_memory.compaction_count(thread_id)

    def _reply_offline(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: implement the deterministic advanced path.

        Pseudocode:
        1. Extract stable profile facts from the incoming message.
        2. Persist those facts into `User.md`.
        3. Append the message into compact memory.
        4. Estimate prompt-context load from `User.md` + summary + recent messages.
        5. Generate a response that can answer long-term recall questions.
        6. Append the assistant reply and update token counters.
        """
        # 1. Extract
        updates = extract_profile_updates(message)

        # 2. Persist
        for key, val in updates.items():
            self.profile_store.upsert_fact(user_id, key, val)

        # 3. Append message to compact memory
        self.compact_memory.append(thread_id, "user", message)

        # 4. Generate response
        assistant_reply = self._offline_response(user_id, thread_id, message)

        # 5. Append response
        self.compact_memory.append(thread_id, "assistant", assistant_reply)

        # 6. Estimate tokens
        prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
        reply_tokens = estimate_tokens(assistant_reply)

        if thread_id not in self.thread_tokens:
            self.thread_tokens[thread_id] = 0
            self.thread_prompt_tokens[thread_id] = 0

        self.thread_tokens[thread_id] += reply_tokens
        self.thread_prompt_tokens[thread_id] += prompt_tokens

        return {
            "response": assistant_reply,
            "tokens": reply_tokens,
            "prompt_tokens": prompt_tokens
        }

    def _estimate_prompt_context_tokens(self, user_id: str, thread_id: str) -> int:
        """Student TODO: estimate the context carried into one turn.

        Hint:
        - Include `User.md`
        - Include compact summary text
        - Include recent kept messages
        """
        profile = self.profile_store.read_text(user_id)
        ctx = self.compact_memory.context(thread_id)
        summary = ctx.get("summary", "")
        messages = ctx.get("messages", [])

        total_text = profile + "\n" + str(summary) + "\n"
        for msg in messages:
            total_text += f"{msg['role']}: {msg['content']}\n"
        return estimate_tokens(total_text)

    def _offline_response(self, user_id: str, thread_id: str, message: str) -> str:
        """Student TODO: return a deterministic answer using persisted memory.

        Make sure the advanced agent can answer questions like:
        - "Mình tên gì?"
        - "Hiện tại mình làm nghề gì?"
        - "Nhắc lại style trả lời mình thích"
        - questions in the long stress dataset
        """
        facts = self.profile_store.facts(user_id)
        lower_msg = message.lower()
        response_parts = []

        if "tên" in lower_msg:
            if "name" in facts:
                response_parts.append(f"Tên của bạn là {facts['name']}.")
            else:
                response_parts.append("Mình chưa biết tên của bạn.")
        if "nghề" in lower_msg or "công việc" in lower_msg or "làm gì" in lower_msg or "engineer" in lower_msg:
            if "job" in facts:
                response_parts.append(f"Nghề nghiệp của bạn là {facts['job']}.")
            else:
                response_parts.append("Mình chưa biết nghề nghiệp của bạn.")
        if "ở đâu" in lower_msg or "nơi ở" in lower_msg or "huế" in lower_msg or "hà nội" in lower_msg or "đà nẵng" in lower_msg:
            if "location" in facts:
                response_parts.append(f"Hiện tại bạn đang ở {facts['location']}.")
            else:
                response_parts.append("Mình chưa biết nơi ở của bạn.")
        if "uống" in lower_msg or "nước" in lower_msg or "cà phê" in lower_msg:
            if "drink" in facts:
                response_parts.append(f"Đồ uống yêu thích của bạn là {facts['drink']}.")
            else:
                response_parts.append("Mình chưa biết đồ uống yêu thích của bạn.")
        if "ăn" in lower_msg or "món" in lower_msg or "mì quảng" in lower_msg:
            if "food" in facts:
                response_parts.append(f"Món ăn yêu thích của bạn là {facts['food']}.")
            else:
                response_parts.append("Mình chưa biết món ăn yêu thích của bạn.")
        if "nuôi" in lower_msg or "con gì" in lower_msg or "corgi" in lower_msg or "bơ" in lower_msg:
            if "pet" in facts:
                response_parts.append(f"Bạn nuôi một bé {facts['pet']}.")
            else:
                response_parts.append("Mình chưa biết bạn nuôi con gì.")
        if "style" in lower_msg or "trả lời" in lower_msg or "bullet" in lower_msg or "ngắn gọn" in lower_msg:
            if "style" in facts:
                response_parts.append(f"Style trả lời bạn thích là {facts['style']}.")
            else:
                response_parts.append("Mình chưa biết style trả lời bạn thích.")
        if "quan tâm" in lower_msg or "sở thích" in lower_msg or "python" in lower_msg or "ai" in lower_msg:
            if "interests" in facts:
                response_parts.append(f"Bạn quan tâm đến {facts['interests']}.")
            else:
                response_parts.append("Mình chưa biết sở thích của bạn.")
        if "mình là ai" in lower_msg or "mô tả" in lower_msg or "tóm tắt" in lower_msg:
            if facts:
                desc = [f"{k}: {v}" for k, v in facts.items()]
                response_parts.append("Thông tin về bạn: " + ", ".join(desc))
            else:
                response_parts.append("Mình chưa biết thông tin gì về bạn.")

        if not response_parts:
            response_parts.append("Chào bạn, mình đã ghi nhớ thông tin bạn chia sẻ.")

        return " ".join(response_parts)

    def _maybe_build_langchain_agent(self):
        """Student TODO: wire a live agent with tools and compact middleware.

        High-level design:
        - `build_chat_model(self.config.model)` for the selected provider
        - `InMemorySaver` for short-term thread state
        - tool to read `User.md`
        - tool to write/edit `User.md`
        - dynamic prompt that injects profile memory
        - summarization middleware for long threads
        """
        try:
            self.langchain_agent = build_chat_model(self.config.model)
        except Exception:
            self.langchain_agent = None

