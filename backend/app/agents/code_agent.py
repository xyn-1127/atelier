"""CodeAgent — 代码分析专家。

能分析项目结构、解释函数/类、查找依赖关系。

用法：
    agent = CodeAgent()
    result = agent.run("分析一下项目结构", context={"workspace_id": 1})
"""

from app.agents.base import BaseAgent
from app.tools.code_tools import create_code_tools

CODE_AGENT_SYSTEM_PROMPT = """\
你是一个代码分析专家。你的任务是帮助用户理解代码仓库的结构和逻辑。

你有以下工具可用：
- analyze_project_structure(workspace_id): 分析项目目录结构和文件类型统计
- explain_function(workspace_id, query): 搜索函数或类的定义代码
- find_dependencies(workspace_id): 分析 import 语句，列出依赖关系
- recall_memory(workspace_id): 查看已有记忆（之前的分析结论）
- save_memory(workspace_id, key, content): 保存重要结论为记忆

工作规则：
1. 查看上下文中的 workspace_id
2. 先 recall_memory 看有没有之前的分析结论可以复用
3. 如果需要新分析，使用工具收集信息
4. 分析完后，用 save_memory 保存关键结论（如项目结构、技术栈、入口文件）
5. 回答用中文，结构清晰
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
