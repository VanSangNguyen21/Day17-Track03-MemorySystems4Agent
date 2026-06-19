from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import LabConfig, load_config
from memory_store import estimate_tokens
from model_provider import build_chat_model


@dataclass
class SessionState:
    messages: list[dict[str, str]] = field(default_factory=list)
    token_usage: int = 0
    prompt_tokens_processed: int = 0


class BaselineAgent:
    """Student TODO: implement Agent A.

    Requirements:
    - Within-session memory only
    - No persistent `User.md`
    - Should forget long-term facts across new threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.sessions: dict[str, SessionState] = {}

        # Initialize the LangChain agent if not forced offline
        self.langchain_agent = None
        self.history_store = {}
        if not self.force_offline:
            self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: return the agent response and token accounting.

        Pseudocode:
        - If a live agent exists, call the live path.
        - Otherwise use a deterministic offline path.
        """
        if self.force_offline or self.langchain_agent is None:
            return self._reply_offline(thread_id, message)

        try:
            config = {"configurable": {"session_id": thread_id}}
            response = self.langchain_agent.invoke({"input": message}, config=config)
            response_text = response.content

            # Token tracking
            reply_tokens = estimate_tokens(response_text)
            
            # Retrieve history to estimate prompt tokens
            history = self.history_store[thread_id]
            messages = history.messages
            
            prompt_text = ""
            for msg in messages[:-1]:  # exclude the last AI response
                prompt_text += f"{msg.type}: {msg.content}\n"
            prompt_tokens = estimate_tokens(prompt_text)

            if thread_id not in self.sessions:
                self.sessions[thread_id] = SessionState()
            session = self.sessions[thread_id]
            session.token_usage += reply_tokens
            session.prompt_tokens_processed += prompt_tokens

            # Save messages in sessions state to keep track of counts
            session.messages.append({"role": "user", "content": message})
            session.messages.append({"role": "assistant", "content": response_text})

            return {
                "response": response_text,
                "tokens": reply_tokens,
                "prompt_tokens": prompt_tokens
            }
        except Exception:
            return self._reply_offline(thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        if thread_id not in self.sessions:
            return 0
        return self.sessions[thread_id].token_usage

    def prompt_token_usage(self, thread_id: str) -> int:
        if thread_id not in self.sessions:
            return 0
        return self.sessions[thread_id].prompt_tokens_processed

    def compaction_count(self, thread_id: str) -> int:
        # Baseline has no compact memory.
        return 0

    def _reply_offline(self, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: implement a simple offline behavior.

        Suggested behavior:
        - Store the new user message in the session
        - Generate a short deterministic reply
        - Update token counts
        - Never remember facts across different thread ids
        """
        if thread_id not in self.sessions:
            self.sessions[thread_id] = SessionState()

        session = self.sessions[thread_id]
        session.messages.append({"role": "user", "content": message})

        # Parse facts only from the current thread's history
        from memory_store import extract_profile_updates
        facts = {}
        for m in session.messages:
            if m["role"] == "user":
                facts.update(extract_profile_updates(m["content"]))

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

        assistant_reply = " ".join(response_parts)
        session.messages.append({"role": "assistant", "content": assistant_reply})

        # Calculations
        reply_tokens = estimate_tokens(assistant_reply)
        session.token_usage += reply_tokens

        prompt_text = ""
        for m in session.messages[:-1]:
            prompt_text += f"{m['role']}: {m['content']}\n"
        prompt_tokens = estimate_tokens(prompt_text)
        session.prompt_tokens_processed += prompt_tokens

        return {
            "response": assistant_reply,
            "tokens": reply_tokens,
            "prompt_tokens": prompt_tokens
        }

    def _maybe_build_langchain_agent(self):
        """Student TODO: optionally wire `create_agent` + `InMemorySaver` here.

        Use `build_chat_model(self.config.model)` so the baseline can run with any supported provider.
        """
        try:
            from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
            from langchain_core.runnables.history import RunnableWithMessageHistory
            from langchain_core.chat_history import InMemoryChatMessageHistory

            model = build_chat_model(self.config.model)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Bạn là một AI assistant hữu ích. Hãy trả lời ngắn gọn, rõ ý và có ví dụ thực tế khi cần thiết."),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}")
            ])
            chain = prompt | model

            def get_session_history(session_id: str):
                if session_id not in self.history_store:
                    self.history_store[session_id] = InMemoryChatMessageHistory()
                return self.history_store[session_id]

            self.langchain_agent = RunnableWithMessageHistory(
                chain,
                get_session_history,
                input_messages_key="input",
                history_messages_key="history"
            )
        except Exception:
            self.langchain_agent = None

