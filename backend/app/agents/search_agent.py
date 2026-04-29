"""SearchAgent — 搜索专家。

能在工作区中进行语义搜索和关键词搜索，回答需要跨文件查找信息的问题。

FileAgent vs SearchAgent:
  FileAgent:   "帮我看看 main.py" → 知道文件名，直接读
  SearchAgent: "项目怎么连接数据库" → 不知道在哪个文件，需要搜索

用法：
    agent = SearchAgent()
    result = agent.run("这个项目的入口在哪？", context={"workspace_id": 1})
"""

from app.agents.base import BaseAgent
from app.tools.search_tools import create_search_tools

SEARCH_AGENT_SYSTEM_PROMPT = """\
你是一个搜索专家。你的任务是在工作区的文件中搜索相关内容来回答用户的问题。

你有以下工具可用：
- semantic_search(workspace_id, query): 语义搜索，用自然语言描述想找的内容
- keyword_search(workspace_id, keyword): 关键词搜索，精确匹配函数名、变量名等

工作规则：
1. 查看上下文中的 workspace_id
2. 根据问题类型选择搜索方式：
   - 用户用自然语言提问（如"怎么连接数据库"）→ 用 semantic_search
   - 用户找特定名称（如"find create_engine"）→ 用 keyword_search
   - 不确定时两种都试
3. 基于搜索结果回答问题，标注来源文件名
4. 如果搜索无结果，告诉用户可能需要先建立索引
5. 回答用中文，简洁清晰
"""


class SearchAgent(BaseAgent):
    """搜索 Agent。"""

    def __init__(self):
        super().__init__(
            name="search_agent",
            description="搜索专家，能在工作区中进行语义搜索和关键词搜索",
            system_prompt=SEARCH_AGENT_SYSTEM_PROMPT,
            tools=create_search_tools(),
        )
