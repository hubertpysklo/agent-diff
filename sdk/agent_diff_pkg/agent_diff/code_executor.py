"""
Code execution proxies for AI agents with automatic network interception.

Provides separate executors for Python and Bash that intercept API calls
to Slack/Linear and route them to Agent Diff test environments.
"""

import subprocess
import os
import json
from typing import Dict, Any, Optional


class BaseExecutorProxy:
    def __init__(
        self,
        environment_id: str,
        base_url: str = "http://localhost:8000",
        token: Optional[str] = None,
    ):
        self.environment_id = environment_id
        self.base_url = base_url
        self.token = token

        # URL mappings for interception
        self.url_mappings = [
            (
                "https://api.slack.com",
                f"{base_url}/api/env/{environment_id}/services/slack/api",
            ),
            (
                "https://slack.com",
                f"{base_url}/api/env/{environment_id}/services/slack",
            ),
            (
                "https://api.linear.app",
                f"{base_url}/api/env/{environment_id}/services/linear",
            ),
        ]

    def _run_code(
        self,
        code: str,
        command: list,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                command,
                input=code,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return {
                "status": "success" if result.returncode == 0 else "error",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": f"Code execution timed out after {timeout} seconds",
                "stdout": "",
                "stderr": "",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Execution failed: {str(e)}",
                "stdout": "",
                "stderr": "",
            }


class PythonExecutorProxy(BaseExecutorProxy):
    def execute(self, code: str) -> Dict[str, Any]:
        """Execute Python code with network interception."""
        wrapper_code = f'''
import sys
import json
import warnings
warnings.filterwarnings("ignore")

url_mappings = {json.dumps(self.url_mappings)}
auth_token = "{self.token or ""}"

# Monkey-patch requests library
try:
    import requests
    original_request = requests.request

    def patch_url_and_headers(url, kwargs):
        for old_url, new_url in url_mappings:
            if old_url in url:
                url = url.replace(old_url, new_url)
                if auth_token:
                    if "headers" not in kwargs:
                        kwargs["headers"] = {{}}
                    kwargs["headers"]["Authorization"] = f"Bearer {{auth_token}}"
                break
        return url, kwargs

    def patched_request(method, url, **kwargs):
        url, kwargs = patch_url_and_headers(url, kwargs)
        return original_request(method, url, **kwargs)

    requests.request = patched_request
    requests.get = lambda url, **kwargs: patched_request("GET", url, **kwargs)
    requests.post = lambda url, **kwargs: patched_request("POST", url, **kwargs)
    requests.put = lambda url, **kwargs: patched_request("PUT", url, **kwargs)
    requests.patch = lambda url, **kwargs: patched_request("PATCH", url, **kwargs)
    requests.delete = lambda url, **kwargs: patched_request("DELETE", url, **kwargs)
except ImportError:
    pass

# Also patch urllib for completeness
try:
    import urllib.request
    import urllib.parse
    original_urlopen = urllib.request.urlopen

    def patched_urlopen(url, *args, **kwargs):
        if isinstance(url, str):
            for old_url, new_url in url_mappings:
                if old_url in url:
                    url = url.replace(old_url, new_url)
                    break
        elif hasattr(url, 'full_url'):
            full_url = url.get_full_url()
            for old_url, new_url in url_mappings:
                if old_url in full_url:
                    url = urllib.request.Request(
                        full_url.replace(old_url, new_url),
                        data=url.data,
                        headers=url.headers
                    )
                    if auth_token:
                        url.add_header('Authorization', f'Bearer {{auth_token}}')
                    break
        return original_urlopen(url, *args, **kwargs)

    urllib.request.urlopen = patched_urlopen
except ImportError:
    pass

# Execute user code
try:
{self._indent_code(code)}
except Exception as e:
    print(f"Error: {{e}}", file=sys.stderr)
    sys.exit(1)
'''
        return self._run_code(wrapper_code, ["python3"])

    def _indent_code(self, code: str) -> str:
        """Indent code for Python wrapper."""
        return "\n".join("    " + line for line in code.split("\n"))


class BashExecutorProxy(BaseExecutorProxy):
    """Bash code executor with curl interception."""

    def execute(self, code: str) -> Dict[str, Any]:
        """Execute Bash code with curl interception."""
        wrapper_code = f"""#!/bin/bash

# Override curl to intercept and modify URLs
curl() {{
    local args=("$@")
    local new_args=()

    for arg in "${{args[@]}}"; do
        modified_arg="$arg"

        if [[ "$arg" == *"https://api.slack.com"* ]]; then
            modified_arg="${{arg//https:\\/\\/api.slack.com/{self.base_url}/api/env/{self.environment_id}/services/slack/api}}"
        elif [[ "$arg" == *"https://api.linear.app"* ]]; then
            modified_arg="${{arg//https:\\/\\/api.linear.app/{self.base_url}/api/env/{self.environment_id}/services/linear}}"
        fi

        new_args+=("$modified_arg")
    done

    # Add auth header if token provided
    {f'new_args+=("-H" "Authorization: Bearer {self.token}")' if self.token else ""}

    # Call real curl with modified arguments
    command curl "${{new_args[@]}}"
}}

export -f curl

# Execute user code
{code}
"""
        return self._run_code(wrapper_code, ["bash"])


# Framework-specific tool factories


def _format_execution_result(
    result: Dict[str, Any], success_msg: str = "Code executed successfully"
) -> str:
    if result["status"] == "success":
        return result["stdout"] or f"{success_msg} (no output)"
    else:
        return f"Error: {result.get('error', result['stderr'])}"


def create_openai_tool(executor: BaseExecutorProxy):
    """Create execution tool for OpenAI Agents SDK."""
    try:
        from agents import function_tool
    except ImportError:
        raise ImportError(
            "OpenAI Agents SDK not installed. Install with: pip install openai-agents"
        )

    # Determine tool type based on executor type
    if isinstance(executor, PythonExecutorProxy):

        @function_tool
        def execute_python(code: str) -> str:
            """Execute Python code with automatic API interception.

            Args:
                code: Python code to execute. Network requests to Slack/Linear APIs are automatically routed to the test environment.
            """
            return _format_execution_result(executor.execute(code))

        return execute_python

    elif isinstance(executor, BashExecutorProxy):

        @function_tool
        def execute_bash(code: str) -> str:
            """Execute Bash commands with automatic curl interception.

            Args:
                code: Bash commands to execute. curl requests to Slack/Linear APIs are automatically routed to the test environment.
            """
            return _format_execution_result(
                executor.execute(code), "Commands executed successfully"
            )

        return execute_bash

    else:
        raise TypeError(f"Unsupported executor type: {type(executor)}")


def create_langchain_tool(executor: BaseExecutorProxy):
    """Create execution tool for LangChain."""
    try:
        from langchain.tools import tool
    except ImportError:
        raise ImportError(
            "LangChain not installed. Install with: pip install langchain"
        )

    # Determine tool type based on executor type
    if isinstance(executor, PythonExecutorProxy):

        @tool
        def execute_python(code: str) -> str:
            """Execute Python code. Network requests to Slack/Linear APIs work automatically.

            Args:
                code: Python code to execute

            Returns:
                The stdout from executing the code, or an error message if execution failed.
            """
            return _format_execution_result(executor.execute(code))

        return execute_python

    elif isinstance(executor, BashExecutorProxy):

        @tool
        def execute_bash(code: str) -> str:
            """Execute Bash commands. curl requests to Slack/Linear APIs work automatically.

            Args:
                code: Bash commands to execute

            Returns:
                The stdout from executing the commands, or an error message if execution failed.
            """
            return _format_execution_result(
                executor.execute(code), "Commands executed successfully"
            )

        return execute_bash

    else:
        raise TypeError(f"Unsupported executor type: {type(executor)}")


def create_smolagents_tool(executor: BaseExecutorProxy):
    """Create execution tool for Hugging Face smolagents."""
    try:
        from smolagents import Tool
    except ImportError:
        raise ImportError(
            "smolagents not installed. Install with: pip install smolagents"
        )

    # Determine tool type based on executor type
    if isinstance(executor, PythonExecutorProxy):

        class PythonExecutorTool(Tool):
            name = "execute_python"
            description = "Execute Python code. API calls to Slack/Linear automatically route to test environment."
            inputs = {"code": {"type": "text", "description": "Python code to execute"}}
            output_type = "text"

            def forward(self, code: str) -> str:
                return _format_execution_result(executor.execute(code))

        return PythonExecutorTool()

    elif isinstance(executor, BashExecutorProxy):

        class BashExecutorTool(Tool):
            name = "execute_bash"
            description = "Execute Bash commands. curl to Slack/Linear APIs automatically routes to test environment."
            inputs = {
                "code": {"type": "text", "description": "Bash commands to execute"}
            }
            output_type = "text"

            def forward(self, code: str) -> str:
                return _format_execution_result(
                    executor.execute(code), "Commands executed successfully"
                )

        return BashExecutorTool()

    else:
        raise TypeError(f"Unsupported executor type: {type(executor)}")
