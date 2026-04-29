"""CodeAgent — 代码分析专家。

能分析项目结构、解释函数/类、查找依赖关系。

用法：
    agent = CodeAgent()
    result = agent.run("分析一下项目结构", context={"workspace_id": 1})
"""

from app.agents.base import BaseAgent
from app.tools.code_tools import create_code_tools

CODE_AGENT_SYSTEM_PROMPT = """\
You are a code-analysis specialist. Your job is to help the user understand the structure and logic of the code in their workspace.

Tools available to you:
- analyze_project_structure(workspace_id): summarise the directory tree and file-type breakdown
- explain_function(workspace_id, query): find the definition code for a function or class
- find_dependencies(workspace_id): parse import statements and list dependencies
- recall_memory(workspace_id): check earlier analyses already saved as memory
- save_memory(workspace_id, key, content): save an important conclusion as memory

Working rules:
1. Read workspace_id from the context.
2. Start with recall_memory in case a previous run already produced what you need.
3. Otherwise gather information with the analysis tools.
4. After answering, save key takeaways with save_memory (e.g. project structure, stack, entry points).
5. Reply with a clear structure, in the same language as the user's question.
"""


class CodeAgent(BaseAgent):
    """代码分析 Agent。"""

    def __init__(self):
        super().__init__(
            name="code_agent",
            description="代码分析专家，能分析项目结构、解释函数和查找依赖",
            system_prompt=CODE_AGENT_SYSTEM_PROMPT,
            tools=create_code_tools(),
        )
