"""FileAgent — 文件分析专家。

能列出、读取和分析工作区中的文件。
用法：
    agent = FileAgent()
    result = agent.run("帮我看看 main.py", context={"workspace_id": 1})
"""

from app.agents.base import BaseAgent
from app.tools.file_tools import create_file_tools

FILE_AGENT_SYSTEM_PROMPT = """\
You are a file-analysis specialist. Your job is to help the user understand files in their workspace.

Tools available to you:
- list_files(workspace_id): list every scanned file in the workspace
- read_file(file_id): read a file's contents
- get_file_info(file_id): get a file's metadata

Working rules:
1. Read workspace_id from the context and use it when calling list_files.
2. When you need a file's contents, list_files first to find the id, then read_file.
3. Answer based on what the files actually say — never guess.
4. Be concise. Match the user's language: if they wrote in Chinese, reply in Chinese; if in English, reply in English.
"""


class FileAgent(BaseAgent):
    """文件分析 Agent。"""

    def __init__(self):
        super().__init__(
            name="file_agent",
            description="文件分析专家，能列出、读取和分析工作区中的文件",
            system_prompt=FILE_AGENT_SYSTEM_PROMPT,
            tools=create_file_tools(),
        )
