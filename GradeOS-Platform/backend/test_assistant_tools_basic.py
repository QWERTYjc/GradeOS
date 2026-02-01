"""
基础测试：验证工具函数基础架构
"""

import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.assistant_tools import ToolParameter, ToolDefinition, ToolRegistry


async def sample_tool_function(student_id: str, limit: int = 10):
    """示例工具函数"""
    return {
        "student_id": student_id,
        "limit": limit,
        "data": ["item1", "item2"]
    }


def test_tool_parameter_creation():
    """测试 ToolParameter 创建"""
    param = ToolParameter(
        name="student_id",
        type="string",
        description="学生 ID",
        required=True
    )
    
    assert param.name == "student_id"
    assert param.type == "string"
    assert param.description == "学生 ID"
    assert param.required is True
    assert param.enum is None
    print("✓ ToolParameter 创建测试通过")


def test_tool_parameter_with_enum():
    """测试带枚举的 ToolParameter"""
    param = ToolParameter(
        name="time_range",
        type="string",
        description="时间范围",
        required=False,
        enum=["week", "month", "semester"]
    )
    
    assert param.enum == ["week", "month", "semester"]
    print("✓ ToolParameter 枚举测试通过")


def test_tool_definition_creation():
    """测试 ToolDefinition 创建"""
    tool = ToolDefinition(
        name="get_grading_history",
        description="查询学生的批改历史",
        parameters=[
            ToolParameter(
                name="student_id",
                type="string",
                description="学生 ID",
                required=True
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="返回结果数量限制",
                required=False
            )
        ],
        function=sample_tool_function
    )
    
    assert tool.name == "get_grading_history"
    assert len(tool.parameters) == 2
    assert callable(tool.function)
    print("✓ ToolDefinition 创建测试通过")


def test_tool_registry_register():
    """测试工具注册"""
    registry = ToolRegistry()
    
    tool = ToolDefinition(
        name="test_tool",
        description="测试工具",
        parameters=[
            ToolParameter(
                name="param1",
                type="string",
                description="参数1",
                required=True
            )
        ],
        function=sample_tool_function
    )
    
    registry.register(tool)
    
    assert len(registry) == 1
    assert "test_tool" in registry
    assert registry.get_tool("test_tool") is not None
    print("✓ 工具注册测试通过")


def test_tool_registry_get_tool():
    """测试获取工具"""
    registry = ToolRegistry()
    
    tool = ToolDefinition(
        name="test_tool",
        description="测试工具",
        parameters=[],
        function=sample_tool_function
    )
    
    registry.register(tool)
    
    retrieved_tool = registry.get_tool("test_tool")
    assert retrieved_tool is not None
    assert retrieved_tool.name == "test_tool"
    
    non_existent = registry.get_tool("non_existent")
    assert non_existent is None
    print("✓ 获取工具测试通过")


def test_tool_registry_list_tools():
    """测试列出所有工具"""
    registry = ToolRegistry()
    
    tool1 = ToolDefinition(
        name="tool1",
        description="工具1",
        parameters=[],
        function=sample_tool_function
    )
    
    tool2 = ToolDefinition(
        name="tool2",
        description="工具2",
        parameters=[],
        function=sample_tool_function
    )
    
    registry.register(tool1)
    registry.register(tool2)
    
    all_tools = registry.get_all_tools()
    assert len(all_tools) == 2
    
    tool_names = registry.list_tool_names()
    assert "tool1" in tool_names
    assert "tool2" in tool_names
    print("✓ 列出工具测试通过")


def test_to_gemini_schema_basic():
    """测试基础 Gemini schema 转换"""
    registry = ToolRegistry()
    
    tool = ToolDefinition(
        name="get_grading_history",
        description="查询学生的批改历史",
        parameters=[
            ToolParameter(
                name="student_id",
                type="string",
                description="学生 ID",
                required=True
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="返回结果数量限制",
                required=False
            )
        ],
        function=sample_tool_function
    )
    
    registry.register(tool)
    
    schemas = registry.to_gemini_schema()
    
    assert len(schemas) == 1
    schema = schemas[0]
    
    # 验证基本结构
    assert schema["name"] == "get_grading_history"
    assert schema["description"] == "查询学生的批改历史"
    assert "parameters" in schema
    
    # 验证参数结构
    params = schema["parameters"]
    assert params["type"] == "object"
    assert "properties" in params
    assert "required" in params
    
    # 验证 properties
    properties = params["properties"]
    assert "student_id" in properties
    assert "limit" in properties
    assert properties["student_id"]["type"] == "string"
    assert properties["limit"]["type"] == "integer"
    
    # 验证 required
    assert "student_id" in params["required"]
    assert "limit" not in params["required"]
    
    print("✓ 基础 Gemini schema 转换测试通过")


def test_to_gemini_schema_with_enum():
    """测试带枚举的 Gemini schema 转换"""
    registry = ToolRegistry()
    
    tool = ToolDefinition(
        name="get_progress_report",
        description="生成学生的学习进度报告",
        parameters=[
            ToolParameter(
                name="student_id",
                type="string",
                description="学生 ID",
                required=True
            ),
            ToolParameter(
                name="time_range",
                type="string",
                description="时间范围",
                required=False,
                enum=["week", "month", "semester"]
            )
        ],
        function=sample_tool_function
    )
    
    registry.register(tool)
    
    schemas = registry.to_gemini_schema()
    schema = schemas[0]
    
    # 验证枚举值
    time_range_prop = schema["parameters"]["properties"]["time_range"]
    assert "enum" in time_range_prop
    assert time_range_prop["enum"] == ["week", "month", "semester"]
    
    print("✓ 带枚举的 Gemini schema 转换测试通过")


def test_to_gemini_schema_multiple_tools():
    """测试多个工具的 schema 转换"""
    registry = ToolRegistry()
    
    tool1 = ToolDefinition(
        name="tool1",
        description="工具1",
        parameters=[
            ToolParameter(name="param1", type="string", description="参数1", required=True)
        ],
        function=sample_tool_function
    )
    
    tool2 = ToolDefinition(
        name="tool2",
        description="工具2",
        parameters=[
            ToolParameter(name="param2", type="integer", description="参数2", required=True)
        ],
        function=sample_tool_function
    )
    
    registry.register(tool1)
    registry.register(tool2)
    
    schemas = registry.to_gemini_schema()
    
    assert len(schemas) == 2
    
    # 验证两个工具都被转换
    tool_names = [s["name"] for s in schemas]
    assert "tool1" in tool_names
    assert "tool2" in tool_names
    
    print("✓ 多工具 Gemini schema 转换测试通过")


def test_gemini_schema_format():
    """测试 Gemini schema 格式完整性"""
    registry = ToolRegistry()
    
    tool = ToolDefinition(
        name="test_tool",
        description="测试工具",
        parameters=[
            ToolParameter(
                name="required_param",
                type="string",
                description="必需参数",
                required=True
            ),
            ToolParameter(
                name="optional_param",
                type="boolean",
                description="可选参数",
                required=False
            )
        ],
        function=sample_tool_function
    )
    
    registry.register(tool)
    schemas = registry.to_gemini_schema()
    schema = schemas[0]
    
    # 验证完整的 schema 结构
    assert isinstance(schema, dict)
    assert "name" in schema
    assert "description" in schema
    assert "parameters" in schema
    
    params = schema["parameters"]
    assert params["type"] == "object"
    assert isinstance(params["properties"], dict)
    assert isinstance(params["required"], list)
    
    # 验证每个属性都有 type 和 description
    for prop_name, prop_value in params["properties"].items():
        assert "type" in prop_value
        assert "description" in prop_value
    
    print("✓ Gemini schema 格式完整性测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始测试工具函数基础架构")
    print("=" * 60)
    
    try:
        test_tool_parameter_creation()
        test_tool_parameter_with_enum()
        test_tool_definition_creation()
        test_tool_registry_register()
        test_tool_registry_get_tool()
        test_tool_registry_list_tools()
        test_to_gemini_schema_basic()
        test_to_gemini_schema_with_enum()
        test_to_gemini_schema_multiple_tools()
        test_gemini_schema_format()
        
        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
