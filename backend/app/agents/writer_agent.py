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
You are a writing specialist. Your job is to produce high-quality Markdown documents based on the user's request.

Tools available to you:
- semantic_search(workspace_id, query): semantic search to learn what's in the workspace
- keyword_search(workspace_id, keyword): keyword search for specific content
- recall_memory(workspace_id): check earlier analyses already saved as memory
- save_note(workspace_id, title): save the document you just wrote as a note (the content of the note is automatically taken from your last output — you only supply a title)

Working rules:
1. Read workspace_id from the context.
2. Start with recall_memory to see if a prior analysis is reusable.
3. If you still need more, search the workspace — at most 2–3 calls, don't loop.
4. Write the complete Markdown document directly into your reply.
5. After writing, you MUST call save_note(workspace_id, title) to persist it.
   This is mandatory — saying "saved" without calling the tool does NOT save it.
   save_note automatically uses whatever Markdown you just wrote; you only pass workspace_id and title.
6. Use proper Markdown structure: headings, lists, tables, code blocks.
7. Write in the same language as the user's question.
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
