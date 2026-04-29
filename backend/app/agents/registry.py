"""Agent 注册表。

集中管理所有可用的 Agent，供 Orchestrator 查阅。
Orchestrator 需要知道"有哪些 Agent、各自擅长什么"才能制定执行计划。
"""

from app.agents.file_agent import FileAgent
from app.agents.search_agent import SearchAgent
from app.agents.code_agent import CodeAgent
from app.agents.writer_agent import WriterAgent

# 所有可用 Agent 的注册信息
# Orchestrator 会把这些描述放进 prompt，让 LLM 决定用哪些
AVAILABLE_AGENTS = {
    "file_agent": {
        "description": "文件分析专家：列出、读取、分析工作区中的文件。适合查看具体文件内容。",
        "class": FileAgent,
    },
    "search_agent": {
        "description": "搜索专家：语义搜索和关键词搜索。适合在工作区中查找特定内容、不知道在哪个文件时使用。",
        "class": SearchAgent,
    },
    "code_agent": {
        "description": "代码分析专家：分析项目结构、解释函数、查找依赖关系。适合理解代码仓库。",
        "class": CodeAgent,
    },
    "writer_agent": {
        "description": "写作专家：生成总结、学习计划、对比报告等 Markdown 文档，并能保存为笔记。",
        "class": WriterAgent,
    },
}


def get_agent(name: str):
    """根据名称实例化一个 Agent。"""
    info = AVAILABLE_AGENTS.get(name)
    if not info:
        return None
    return info["class"]()


def get_agents_description() -> str:
    """生成所有 Agent 的描述文本，给 Orchestrator 的 prompt 用。"""
    lines = []
    for name, info in AVAILABLE_AGENTS.items():
        lines.append(f"- {name}: {info['description']}")
    return "\n".join(lines)
