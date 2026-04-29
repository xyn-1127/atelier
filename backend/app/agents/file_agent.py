"""FileAgent — 文件分析专家。

能列出、读取和分析工作区中的文件。
用法：
    agent = FileAgent()
    result = agent.run("帮我看看 main.py", context={"workspace_id": 1})
"""

from app.agents.base import BaseAgent
from app.tools.file_tools import create_file_tools

FILE_AGENT_SYSTEM_PROMPT = """\
你是一个文件分析专家。你的任务是帮助用户理解工作区中的文件。

你有以下工具可用：
- list_files(workspace_id): 列出工作区中的所有文件
- read_file(file_id): 读取文件内容
- get_file_info(file_id): 获取文件详细信息

工作规则：
1. 查看上下文中的 workspace_id，用于调用 list_files
2. 需要了解文件内容时，先 list_files 找到文件 ID，再 read_file 读取
3. 基于文件实际内容回答问题，不要猜测
4. 回答要简洁清晰，用中文
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
