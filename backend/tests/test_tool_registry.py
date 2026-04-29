"""工具注册中心测试。"""

from app.tools.registry import Tool, ToolRegistry, register_tool, tool_registry


class TestToolRegistry:
    """ToolRegistry 核心功能测试。"""

    def test_register_and_get(self):
        """注册工具后能查到。"""
        registry = ToolRegistry()

        tool = Tool(
            name="double",
            description="返回两倍的值",
            parameters={"x": {"type": "integer", "description": "输入数字"}},
            function=lambda x: str(x * 2),
        )
        registry.register(tool)

        assert registry.get("double") is not None
        assert registry.get("double").name == "double"
        assert registry.get("nonexistent") is None

    def test_list_all(self):
        """列出所有工具。"""
        registry = ToolRegistry()

        registry.register(Tool(name="t1", description="d1", parameters={}, function=lambda: ""))
        registry.register(Tool(name="t2", description="d2", parameters={}, function=lambda: ""))

        all_tools = registry.list_all()
        assert len(all_tools) == 2
        names = [t.name for t in all_tools]
        assert "t1" in names
        assert "t2" in names

    def test_overwrite_warning(self):
        """重复注册同名工具会覆盖。"""
        registry = ToolRegistry()

        registry.register(Tool(name="dup", description="v1", parameters={}, function=lambda: "v1"))
        registry.register(Tool(name="dup", description="v2", parameters={}, function=lambda: "v2"))

        assert registry.get("dup").description == "v2"
        assert len(registry.list_all()) == 1


class TestToOpenAITools:
    """to_openai_tools() 格式转换测试。"""

    def test_basic_format(self):
        """基本格式正确。"""
        registry = ToolRegistry()
        registry.register(Tool(
            name="read_file",
            description="读取文件内容",
            parameters={"file_id": {"type": "integer", "description": "文件 ID"}},
            function=lambda file_id: "",
        ))

        tools = registry.to_openai_tools()

        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "read_file"
        assert tools[0]["function"]["description"] == "读取文件内容"

        params = tools[0]["function"]["parameters"]
        assert params["type"] == "object"
        assert "file_id" in params["properties"]
        assert params["properties"]["file_id"]["type"] == "integer"
        assert "file_id" in params["required"]

    def test_optional_parameter(self):
        """可选参数不出现在 required 中。"""
        registry = ToolRegistry()
        registry.register(Tool(
            name="search",
            description="搜索",
            parameters={
                "query": {"type": "string", "description": "搜索词"},
                "limit": {"type": "integer", "description": "最大数量", "required": False},
            },
            function=lambda query, limit=10: "",
        ))

        tools = registry.to_openai_tools()
        params = tools[0]["function"]["parameters"]

        assert "query" in params["required"]
        assert "limit" not in params["required"]

    def test_empty_registry(self):
        """空注册中心返回空列表。"""
        registry = ToolRegistry()
        assert registry.to_openai_tools() == []


class TestExecute:
    """execute() 工具执行测试。"""

    def test_execute_success(self):
        """正常执行工具。"""
        registry = ToolRegistry()
        registry.register(Tool(
            name="add",
            description="加法",
            parameters={
                "a": {"type": "integer", "description": "第一个数"},
                "b": {"type": "integer", "description": "第二个数"},
            },
            function=lambda a, b: str(a + b),
        ))

        result = registry.execute("add", {"a": 3, "b": 5})
        assert result == "8"

    def test_execute_auto_json(self):
        """返回非字符串时自动转 JSON。"""
        registry = ToolRegistry()
        registry.register(Tool(
            name="get_info",
            description="获取信息",
            parameters={},
            function=lambda: {"name": "测试", "value": 42},
        ))

        result = registry.execute("get_info", {})
        assert isinstance(result, str)
        assert "测试" in result
        assert "42" in result

    def test_execute_not_found(self):
        """执行不存在的工具时抛 ValueError。"""
        registry = ToolRegistry()

        try:
            registry.execute("nonexistent", {})
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "not found" in str(e)

    def test_execute_handles_error(self):
        """工具执行出错时返回错误信息，不抛异常。"""
        registry = ToolRegistry()
        registry.register(Tool(
            name="broken",
            description="坏掉的工具",
            parameters={},
            function=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        ))

        # 用一个真正会抛异常的函数
        def explode():
            raise RuntimeError("Something went wrong")

        registry._tools["broken"].function = explode

        result = registry.execute("broken", {})
        assert "工具执行失败" in result
        assert "Something went wrong" in result


class TestRegisterToolDecorator:
    """@register_tool 装饰器测试。"""

    def test_decorator_registers_tool(self):
        """装饰器能正确注册工具。"""
        before_count = len(tool_registry.list_all())

        @register_tool(
            name="test_decorator_tool",
            description="测试装饰器",
            parameters={"msg": {"type": "string", "description": "消息"}},
        )
        def my_tool(msg: str) -> str:
            return f"echo: {msg}"

        assert len(tool_registry.list_all()) == before_count + 1
        assert tool_registry.get("test_decorator_tool") is not None

    def test_decorator_preserves_function(self):
        """装饰器不改变原函数行为。"""

        @register_tool(
            name="test_preserve_func",
            description="测试",
            parameters={"x": {"type": "integer", "description": "数字"}},
        )
        def double(x: int) -> str:
            return str(x * 2)

        # 直接调用原函数
        assert double(5) == "10"

        # 通过 registry 执行
        result = tool_registry.execute("test_preserve_func", {"x": 5})
        assert result == "10"
