"""后台 LLM 生成管理器。

LLM 调用在后台线程中运行，不依赖 HTTP 连接。
客户端断开后生成继续进行，重连时可从头回放所有 chunk。

线程安全设计：
- _lock: 保护 chunks/full_content/full_reasoning/status 的读写
- _event: 通知等待中的消费者"有新数据了"
- iter_chunks 在锁外 yield，避免持锁挂起
- 用 Event 替代 Condition，避免 GeneratorExit + wait() 的锁状态不一致
"""

import logging
import threading
import time

from app.llm.client import chat_completion_stream, chat_completion_stream_reasoning

logger = logging.getLogger(__name__)


class GenerationState:
    """一次 LLM 生成的状态，线程安全。"""

    def __init__(self, message_id: int, chat_id: int):
        self.message_id = message_id
        self.chat_id = chat_id
        self.chunks: list[tuple[str, str]] = []  # [(type, data), ...]
        self.full_content = ""
        self.full_reasoning = ""
        self.status = "running"  # "running" | "done" | "error"
        self.error = None
        self._lock = threading.Lock()
        self._event = threading.Event()  # 有新 chunk 或状态变化时 set

    def add_chunk(self, chunk_type: str, data: str):
        with self._lock:
            self.chunks.append((chunk_type, data))
            if chunk_type == "reasoning_chunk":
                self.full_reasoning += data
            elif chunk_type == "chunk":
                self.full_content += data
        self._event.set()

    def mark_done(self):
        with self._lock:
            self.status = "done"
        self._event.set()

    def mark_error(self, error: str):
        with self._lock:
            self.status = "error"
            self.error = error
        self._event.set()

    def get_snapshot(self, offset: int = 0) -> tuple[list[tuple[str, str]], str]:
        """线程安全地获取从 offset 开始的新 chunk 和当前状态。"""
        with self._lock:
            new_chunks = list(self.chunks[offset:])
            status = self.status
        return new_chunks, status

    def get_result(self) -> tuple[str, str, str, str | None]:
        """线程安全地获取最终结果。"""
        with self._lock:
            return self.full_content, self.full_reasoning, self.status, self.error

    def iter_chunks(self, offset: int = 0, max_idle_seconds: int = 300):
        """从 offset 开始逐个 yield chunk，阻塞等待新 chunk。

        关键设计：
        - yield 在锁外执行（不会持锁挂起阻塞后台线程）
        - 用 Event.wait() 而非 Condition.wait()（GeneratorExit 安全）
        """
        last_chunk_time = time.monotonic()

        while True:
            # 先清除 event，再读快照（避免丢失信号）
            self._event.clear()
            new_chunks, status = self.get_snapshot(offset)

            # 有新 chunk，在锁外逐个 yield
            if new_chunks:
                offset += len(new_chunks)
                last_chunk_time = time.monotonic()
                for chunk in new_chunks:
                    yield chunk

            # 所有 chunk 消费完 且 生成已结束
            if status != "running" and not new_chunks:
                # 可能在 yield 期间又产生了新 chunk，再检查一次
                remaining, _ = self.get_snapshot(offset)
                for chunk in remaining:
                    yield chunk
                return

            # 没有新 chunk 且仍在运行，等待通知
            if not new_chunks:
                if time.monotonic() - last_chunk_time > max_idle_seconds:
                    logger.warning("iter_chunks timed out after %ds idle for message %d",
                                   max_idle_seconds, self.message_id)
                    return
                # Event.wait() 不涉及锁，GeneratorExit 安全
                self._event.wait(timeout=2.0)


class GenerationManager:
    """管理所有后台 LLM 生成任务的单例。"""

    def __init__(self):
        self._generations: dict[int, GenerationState] = {}
        self._lock = threading.Lock()

    def start(self, message_id: int, chat_id: int,
              messages: list[dict], use_thinking: bool) -> GenerationState:
        """启动后台生成，返回 GenerationState 供 SSE 端点读取。"""
        state = GenerationState(message_id, chat_id)
        with self._lock:
            self._generations[message_id] = state

        thread = threading.Thread(
            target=self._run,
            args=(state, messages, use_thinking),
            daemon=True,
        )
        thread.start()
        return state

    def get(self, message_id: int) -> GenerationState | None:
        with self._lock:
            return self._generations.get(message_id)

    def _run(self, state: GenerationState, messages: list[dict], use_thinking: bool):
        """后台线程：调用 LLM 流式 API，收集 chunk。"""
        try:
            if use_thinking:
                for chunk_type, chunk_text in chat_completion_stream_reasoning(messages):
                    if chunk_type == "reasoning":
                        state.add_chunk("reasoning_chunk", chunk_text)
                    else:
                        state.add_chunk("chunk", chunk_text)
            else:
                for chunk_text in chat_completion_stream(messages):
                    state.add_chunk("chunk", chunk_text)

            state.mark_done()
        except Exception as e:
            logger.error("Background LLM generation failed: %s", e)
            state.mark_error(str(e))

        # 保存到数据库
        self._save_to_db(state)

        # 5 分钟后清理内存
        def cleanup():
            time.sleep(300)
            with self._lock:
                self._generations.pop(state.message_id, None)

        threading.Thread(target=cleanup, daemon=True).start()

    def _save_to_db(self, state: GenerationState):
        """生成完成后写入数据库。"""
        try:
            from app.db.session import SessionLocal
            from app.models.message import Message

            content, reasoning, status, _ = state.get_result()

            db = SessionLocal()
            try:
                msg = db.get(Message, state.message_id)
                if msg:
                    msg.content = content if content else "(生成失败)"
                    msg.reasoning_content = reasoning if reasoning else None
                    msg.status = "done" if status == "done" else "error"
                    db.commit()
                    logger.info("Saved generation result for message %d (status=%s, content_len=%d)",
                                state.message_id, status, len(content))
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to save generation result for message %d: %s",
                         state.message_id, e)


# 全局单例
generation_manager = GenerationManager()
