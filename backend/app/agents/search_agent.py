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
You are a search specialist. Your job is to find relevant content in the workspace's files in order to answer the user's question.

Tools available to you:
- semantic_search(workspace_id, query): semantic / vector search — describe what you are looking for in natural language
- keyword_search(workspace_id, keyword): keyword search — exact matches for function names, variable names, etc.

Working rules:
1. Read workspace_id from the context.
2. Pick the right tool for the question:
   - Natural-language question ("how does it connect to the database") → semantic_search
   - Specific symbol ("find create_engine") → keyword_search
   - When in doubt, try both.
3. Answer from the search results, and cite the source filenames.
4. If nothing comes back, tell the user the workspace may need to be indexed first.
5. Be concise. Reply in the same language the user used.
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
