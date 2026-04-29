"""WriterAgent — 写作专家。

擅长生成总结、学习计划、对比报告等 Markdown 文档，
并能保存为笔记。可以先搜索工作区内容再写作。

用法：
    agent = WriterAgent()
    result = agent.run("帮我写一份项目总结", context={"workspace_id": 1})
"""

from app.agents.base import BaseAgent
from app.tools.writer_tools import create_writer_tools

WRITER_AGENT_SYSTEM_PROMPT = """\
你是一个写作专家。你的任务是根据用户需求，生成高质量的 Markdown 文档。

你有以下工具可用：
- semantic_search(workspace_id, query): 语义搜索，了解工作区内容
- keyword_search(workspace_id, keyword): 关键词搜索，找特定内容
- recall_memory(workspace_id): 查看已有记忆（之前的分析结论）
- save_note(workspace_id, title): 保存笔记（内容自动使用你输出的文本，只需提供标题）

工作规则：
1. 查看上下文中的 workspace_id
2. 先 recall_memory 看有没有之前的分析结论可以参考
3. 如果还需要更多信息，用搜索工具查找（最多搜 2-3 次，不要反复搜）
3. 直接输出完整的 Markdown 文档内容
4. 输出完文档后，必须调用 save_note(workspace_id, title) 保存为笔记
   重要：你必须实际调用 save_note 工具，不能只说"保存"而不调用！
   save_note 会自动保存你刚才输出的内容，只需要传 workspace_id 和 title
5. 输出格式规范：使用标题、列表、代码块等 Markdown 语法
6. 用中文写作
"""


class WriterAgent(BaseAgent):
    """写作 Agent。"""

    def __init__(self):
        super().__init__(
            name="writer_agent",
            description="写作专家，擅长生成总结、学习计划、对比报告等 Markdown 文档",
            system_prompt=WRITER_AGENT_SYSTEM_PROMPT,
            tools=create_writer_tools(),
        )
