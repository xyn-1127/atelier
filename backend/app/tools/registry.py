"""工具注册中心。

Agent 通过工具与外部世界交互（读文件、查数据库、搜索等）。
本模块提供统一的工具注册、查找和执行机制。

核心概念：
- Tool: 一个工具的定义（名称、描述、参数、执行函数）
- ToolRegistry: 管理所有工具的注册中心
- @register_tool: 装饰器，把普通函数注册为工具
"""

import json
import logging
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """一个可被 Agent 调用的工具。

    属性：
        name: 工具名称，如 "read_file"（LLM 通过这个名字来调用工具）
        description: 工具描述（给 LLM 看，让它判断什么时候该用这个工具）
        parameters: 参数定义，格式：
            {
                "file_id": {"type": "integer", "description": "文件 ID"},
                "max_lines": {"type": "integer", "description": "最大行数", "required": False},
            }
            每个参数默认 required=True
        function: 实际执行的 Python 函数
    """
    name: str
    description: str
    parameters: dict
    function: Callable


class ToolRegistry:
    """工具注册中心，管理所有可用工具。"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册一个工具。"""
        if tool.name in self._tools:
            logger.warning("Tool '%s' already registered, overwriting", tool.name)
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s", tool.name)

    def get(self, name: str) -> Tool | None:
        """按名字查找工具。"""
        return self._tools.get(name)

    def list_all(self) -> list[Tool]:
        """列出所有已注册工具。"""
        return list(self._tools.values())

    def to_openai_tools(self) -> list[dict]:
        """转成 OpenAI/DeepSeek function calling 格式。

        返回示例：
        [{
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取文件内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "integer", "description": "文件 ID"}
                    },
                    "required": ["file_id"]
                }
            }
        }]
        """
        result = []
        for tool in self._tools.values():
            properties = {}
            required = []

            for param_name, param_info in tool.parameters.items():
                properties[param_name] = {
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                }
                if param_info.get("required", True):
                    required.append(param_name)

            result.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })
        return result

    def execute(self, name: str, arguments: dict) -> str:
        """执行工具，返回字符串结果。

        如果工具函数返回非字符串，自动转 JSON。
        如果执行出错，返回错误信息（不抛异常，让 Agent 继续运行）。
        """
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")

        logger.info("Executing tool: %s(%s)", name, arguments)
        try:
            result = tool.function(**arguments)
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)
            logger.info("Tool %s executed successfully, result length=%d", name, len(result))
            return result
        except Exception as e:
            logger.error("Tool '%s' execution failed: %s", name, e)
            return f"工具执行失败: {e}"


# 全局注册中心（单例）
tool_registry = ToolRegistry()


def register_tool(name: str, description: str, parameters: dict):
    """装饰器：把普通函数注册为工具。

    用法：
        @register_tool(
            name="read_file",
            description="读取指定文件的内容",
            parameters={
                "file_id": {"type": "integer", "description": "文件 ID"}
            }
        )
        def read_file(file_id: int) -> str:
            ...

    装饰器做了两件事：
    1. 创建 Tool 对象，注册到全局 tool_registry
    2. 返回原函数（不改变函数行为，直接调用也可以）
    """
    def decorator(func: Callable) -> Callable:
        tool = Tool(
            name=name,
            description=description,
            parameters=parameters,
            function=func,
        )
        tool_registry.register(tool)
        return func
    return decorator
