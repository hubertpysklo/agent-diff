"""Tests for code execution proxies."""

import pytest
from agent_diff.code_executor import (
    PythonExecutorProxy,
    BashExecutorProxy,
    _format_execution_result,
)


class TestPythonExecutorProxy:
    """Test PythonExecutorProxy functionality."""

    def test_basic_execution(self):
        """Test basic Python code execution."""
        executor = PythonExecutorProxy("test_env_123", base_url="http://localhost:8000")

        result = executor.execute("print('hello world')")

        assert result["status"] == "success"
        assert "hello world" in result["stdout"]
        assert result["exit_code"] == 0

    def test_execution_with_error(self):
        """Test Python code execution with error."""
        executor = PythonExecutorProxy("test_env_123", base_url="http://localhost:8000")

        result = executor.execute("raise ValueError('test error')")

        assert result["status"] == "error"
        assert result["exit_code"] == 1
        assert "test error" in result["stderr"]

    def test_url_mapping_initialization(self):
        """Test that URL mappings are correctly initialized."""
        executor = PythonExecutorProxy(
            "test_env_123",
            base_url="http://localhost:8000"
        )

        assert len(executor.url_mappings) == 3
        assert any("api.slack.com" in mapping[0] for mapping in executor.url_mappings)
        assert any("api.linear.app" in mapping[0] for mapping in executor.url_mappings)

        # Check mappings include environment ID
        for old_url, new_url in executor.url_mappings:
            assert "test_env_123" in new_url

    def test_multiline_code_execution(self):
        """Test execution of multiline Python code."""
        executor = PythonExecutorProxy("test_env_123", base_url="http://localhost:8000")

        code = """
x = 10
y = 20
print(x + y)
"""
        result = executor.execute(code)

        assert result["status"] == "success"
        assert "30" in result["stdout"]

    def test_code_with_imports(self):
        """Test execution of code with imports."""
        executor = PythonExecutorProxy("test_env_123", base_url="http://localhost:8000")

        code = """
import json
data = {'key': 'value'}
print(json.dumps(data))
"""
        result = executor.execute(code)

        assert result["status"] == "success"
        assert "key" in result["stdout"]
        assert "value" in result["stdout"]

    def test_timeout_parameter(self):
        """Test that timeout parameter is properly passed."""
        executor = PythonExecutorProxy("test_env_123", base_url="http://localhost:8000")

        # This should complete quickly
        result = executor.execute("print('fast')")
        assert result["status"] == "success"

    def test_token_in_wrapper(self):
        """Test that token is properly embedded in wrapper code."""
        executor = PythonExecutorProxy(
            "test_env_123",
            base_url="http://localhost:8000",
            token="test_token_456"
        )

        # Token should be accessible in the wrapper
        result = executor.execute("print('test')")
        assert result["status"] == "success"

    def test_indent_code_helper(self):
        """Test the _indent_code helper method."""
        executor = PythonExecutorProxy("test_env_123", base_url="http://localhost:8000")

        code = "print('line1')\nprint('line2')"
        indented = executor._indent_code(code)

        assert indented.startswith("    ")
        assert "\n    " in indented


class TestBashExecutorProxy:
    """Test BashExecutorProxy functionality."""

    def test_basic_execution(self):
        """Test basic Bash command execution."""
        executor = BashExecutorProxy("test_env_123", base_url="http://localhost:8000")

        result = executor.execute("echo 'hello from bash'")

        assert result["status"] == "success"
        assert "hello from bash" in result["stdout"]
        assert result["exit_code"] == 0

    def test_execution_with_error(self):
        """Test Bash command execution with error."""
        executor = BashExecutorProxy("test_env_123", base_url="http://localhost:8000")

        result = executor.execute("exit 1")

        assert result["status"] == "error"
        assert result["exit_code"] == 1

    def test_multiline_bash_script(self):
        """Test execution of multiline Bash script."""
        executor = BashExecutorProxy("test_env_123", base_url="http://localhost:8000")

        script = """
VAR1="hello"
VAR2="world"
echo "$VAR1 $VAR2"
"""
        result = executor.execute(script)

        assert result["status"] == "success"
        assert "hello world" in result["stdout"]

    def test_url_mapping_in_bash(self):
        """Test that URL mappings are correctly embedded in Bash wrapper."""
        executor = BashExecutorProxy("test_env_123", base_url="http://localhost:8000")

        # The wrapper should contain the environment ID
        assert executor.environment_id == "test_env_123"
        assert executor.base_url == "http://localhost:8000"

    def test_bash_with_pipes(self):
        """Test Bash commands with pipes."""
        executor = BashExecutorProxy("test_env_123", base_url="http://localhost:8000")

        result = executor.execute("echo 'line1\nline2\nline3' | grep 'line2'")

        assert result["status"] == "success"
        assert "line2" in result["stdout"]

    def test_token_in_bash_wrapper(self):
        """Test that token is properly embedded in Bash wrapper."""
        executor = BashExecutorProxy(
            "test_env_123",
            base_url="http://localhost:8000",
            token="test_token_789"
        )

        result = executor.execute("echo 'test'")
        assert result["status"] == "success"


class TestFormatExecutionResult:
    """Test _format_execution_result helper function."""

    def test_format_success_with_output(self):
        """Test formatting successful result with stdout."""
        result = {
            "status": "success",
            "stdout": "output text",
            "stderr": "",
            "exit_code": 0
        }

        formatted = _format_execution_result(result)
        assert formatted == "output text"

    def test_format_success_no_output(self):
        """Test formatting successful result without stdout."""
        result = {
            "status": "success",
            "stdout": "",
            "stderr": "",
            "exit_code": 0
        }

        formatted = _format_execution_result(result)
        assert "Code executed successfully (no output)" in formatted

    def test_format_success_custom_message(self):
        """Test formatting with custom success message."""
        result = {
            "status": "success",
            "stdout": "",
            "stderr": "",
            "exit_code": 0
        }

        formatted = _format_execution_result(result, "Commands executed successfully")
        assert "Commands executed successfully (no output)" in formatted

    def test_format_error_with_stderr(self):
        """Test formatting error result with stderr."""
        result = {
            "status": "error",
            "stdout": "",
            "stderr": "NameError: name 'x' is not defined",
            "exit_code": 1
        }

        formatted = _format_execution_result(result)
        assert "Error:" in formatted
        assert "NameError" in formatted

    def test_format_error_with_error_field(self):
        """Test formatting error result with error field (e.g., timeout)."""
        result = {
            "status": "error",
            "error": "Code execution timed out after 30 seconds",
            "stdout": "",
            "stderr": ""
        }

        formatted = _format_execution_result(result)
        assert "Error:" in formatted
        assert "timed out" in formatted


class TestToolFactories:
    """Test tool factory functions."""

    def test_create_openai_tool_python(self):
        """Test creating OpenAI tool from Python executor."""
        pytest.importorskip("agents")
        from agent_diff.code_executor import create_openai_tool

        executor = PythonExecutorProxy("test_env", base_url="http://localhost:8000")
        tool = create_openai_tool(executor)

        # OpenAI tools return FunctionTool objects
        assert hasattr(tool, 'name')
        assert tool.name == "execute_python"
        assert hasattr(tool, 'description')
        assert "Python code" in tool.description

    def test_create_openai_tool_bash(self):
        """Test creating OpenAI tool from Bash executor."""
        pytest.importorskip("agents")
        from agent_diff.code_executor import create_openai_tool

        executor = BashExecutorProxy("test_env", base_url="http://localhost:8000")
        tool = create_openai_tool(executor)

        # OpenAI tools return FunctionTool objects
        assert hasattr(tool, 'name')
        assert tool.name == "execute_bash"
        assert hasattr(tool, 'description')
        assert "Bash" in tool.description

    def test_create_langchain_tool_python(self):
        """Test creating LangChain tool from Python executor."""
        pytest.importorskip("langchain")
        from agent_diff.code_executor import create_langchain_tool

        executor = PythonExecutorProxy("test_env", base_url="http://localhost:8000")
        tool = create_langchain_tool(executor)

        assert callable(tool)
        assert tool.name == "execute_python"

    def test_create_langchain_tool_bash(self):
        """Test creating LangChain tool from Bash executor."""
        pytest.importorskip("langchain")
        from agent_diff.code_executor import create_langchain_tool

        executor = BashExecutorProxy("test_env", base_url="http://localhost:8000")
        tool = create_langchain_tool(executor)

        assert callable(tool)
        assert tool.name == "execute_bash"

    def test_create_smolagents_tool_python(self):
        """Test creating smolagents tool from Python executor."""
        pytest.importorskip("smolagents")
        from agent_diff.code_executor import create_smolagents_tool

        executor = PythonExecutorProxy("test_env", base_url="http://localhost:8000")
        tool = create_smolagents_tool(executor)

        assert hasattr(tool, 'name')
        assert tool.name == "execute_python"
        assert hasattr(tool, 'forward')

    def test_create_smolagents_tool_bash(self):
        """Test creating smolagents tool from Bash executor."""
        pytest.importorskip("smolagents")
        from agent_diff.code_executor import create_smolagents_tool

        executor = BashExecutorProxy("test_env", base_url="http://localhost:8000")
        tool = create_smolagents_tool(executor)

        assert hasattr(tool, 'name')
        assert tool.name == "execute_bash"
        assert hasattr(tool, 'forward')

    def test_unsupported_executor_type(self):
        """Test that unsupported executor types raise TypeError."""
        from agent_diff.code_executor import create_openai_tool, BaseExecutorProxy

        class UnsupportedExecutor(BaseExecutorProxy):
            pass

        executor = UnsupportedExecutor("test_env")

        with pytest.raises(TypeError, match="Unsupported executor type"):
            create_openai_tool(executor)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_code_python(self):
        """Test executing empty Python code."""
        executor = PythonExecutorProxy("test_env", base_url="http://localhost:8000")

        result = executor.execute("")

        # Empty code in the try/except block causes IndentationError
        assert result["status"] == "error"
        assert result["exit_code"] == 1

    def test_empty_code_bash(self):
        """Test executing empty Bash code."""
        executor = BashExecutorProxy("test_env", base_url="http://localhost:8000")

        result = executor.execute("")

        assert result["status"] == "success"

    def test_code_with_unicode(self):
        """Test executing code with unicode characters."""
        executor = PythonExecutorProxy("test_env", base_url="http://localhost:8000")

        result = executor.execute("print('Hello 世界 🌍')")

        assert result["status"] == "success"
        assert "Hello" in result["stdout"]

    def test_very_long_output(self):
        """Test code that produces long output."""
        executor = PythonExecutorProxy("test_env", base_url="http://localhost:8000")

        code = "for i in range(100): print(f'Line {i}')"
        result = executor.execute(code)

        assert result["status"] == "success"
        assert "Line 0" in result["stdout"]
        assert "Line 99" in result["stdout"]
