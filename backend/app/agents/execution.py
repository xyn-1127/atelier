"""Agent 后台执行管理器。

和 llm/generation.py 的 GenerationManager 同一个设计思路：
- Agent 在后台线程中执行，不依赖 HTTP 连接
- 事件存在内存中，断线重连时从头回放
- 线程安全：Lock 保护事件列表，Event 通知消费者

事件格式：{"type": "chunk", "data": "...", "step_index": 0}
即完整的 SSE JSON 对象，存什么就推什么。
"""

import json
import logging
import threading
import time

logger = logging.getLogger(__name__)


class AgentExecutionState:
    """一次 Agent 执行的状态，线程安全。"""

    def __init__(self, message_id: int):
        self.message_id = message_id
        self.events: list[str] = []  # 存的是 JSON 字符串（每行一个 SSE 事件）
        self.status = "running"      # "running" | "done" | "error"
        self._lock = threading.Lock()
        self._event = threading.Event()

    def add_event(self, sse_line: str):
        """添加一条 SSE 事件（JSON 字符串）。"""
        with self._lock:
            self.events.append(sse_line)
        self._event.set()

    def mark_done(self):
        with self._lock:
            self.status = "done"
        self._event.set()

    def mark_error(self):
        with self._lock:
            self.status = "error"
        self._event.set()

    def iter_events(self, offset: int = 0, max_idle_seconds: int = 300):
        """从 offset 开始 yield 事件，阻塞等待新事件。

        和 GenerationState.iter_chunks 同样的设计：
        - yield 在锁外（不持锁挂起）
        - 用 Event.wait() 替代 Condition.wait()（GeneratorExit 安全）
        """
        last_event_time = time.monotonic()

        while True:
            self._event.clear()

            with self._lock:
                new_events = list(self.events[offset:])
                status = self.status

            if new_events:
                offset += len(new_events)
                last_event_time = time.monotonic()
                for ev in new_events:
                    yield ev

            if status in ("done", "error") and not new_events:
                return

            if time.monotonic() - last_event_time > max_idle_seconds:
                logger.warning("AgentExecution %d: idle timeout", self.message_id)
                return

            self._event.wait(timeout=0.5)


class AgentExecutionManager:
    """管理所有正在执行的 Agent 任务。"""

    def __init__(self):
        self._states: dict[int, AgentExecutionState] = {}
        self._lock = threading.Lock()

    def start(self, message_id: int, run_fn, on_error=None) -> AgentExecutionState:
        """启动后台 Agent 执行。

        run_fn: callable(state)，在其中调用 state.add_event() 推送事件。
        on_error: callable(message_id, error_str)，异常时落盘用。
        """
        state = AgentExecutionState(message_id)
        with self._lock:
            self._states[message_id] = state

        def _run():
            try:
                run_fn(state)
                state.mark_done()
            except Exception as e:
                logger.error("AgentExecution %d failed: %s", message_id, e)
                state.add_event(json.dumps({"type": "error", "data": str(e)}) + "\n")
                state.mark_error()
                # 异常时也把状态写回数据库
                if on_error:
                    try:
                        on_error(message_id, str(e))
                    except Exception as db_err:
                        logger.error("AgentExecution %d on_error failed: %s", message_id, db_err)
            finally:
                threading.Timer(300, self._cleanup, args=[message_id]).start()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return state

    def get(self, message_id: int) -> AgentExecutionState | None:
        with self._lock:
            return self._states.get(message_id)

    def _cleanup(self, message_id: int):
        with self._lock:
            self._states.pop(message_id, None)
        logger.info("AgentExecution %d: cleaned up", message_id)


agent_execution_manager = AgentExecutionManager()
