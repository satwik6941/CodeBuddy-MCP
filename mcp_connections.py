import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Dict, Any, List
import docker_interpreter
from dotenv import load_dotenv

load_dotenv()

# Global state
mcp_servers = {}
tool_to_server_map = {}
exit_stack = []
docker_enabled = False
vercel_enabled = False


async def connect_github_server(github_token: str):
    """Connect to GitHub MCP server"""
    print("🔌 Connecting to GitHub server...")

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")}
    )

    await _connect_server("github", server_params)


async def connect_render_server():
    """Connect to Render MCP server"""
    print("🔌 Connecting to Render server...")

    server_params = StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "mcp-remote",
            "https://mcp.render.com/mcp",
            "--header",
            f"Authorization: Bearer {os.getenv('RENDER_API_KEY')}"
        ],
    )

    await _connect_server("render", server_params)


def setup_docker(workspace_path: str = "./workspace"):
    """Setup Docker container for code execution (not async)"""
    global docker_enabled

    docker_interpreter.connect_docker(workspace_path)
    docker_enabled = True

    # Map Docker tools
    for tool in docker_interpreter.get_docker_tools():
        tool_to_server_map[tool["name"]] = "docker"


def setup_vercel():
    """Setup Vercel CLI inside Docker container"""
    global vercel_enabled

    vercel_token = os.getenv("VERCEL_TOKEN")
    if not vercel_token:
        print("⚠️ VERCEL_TOKEN not found in .env — skipping Vercel setup")
        return

    if not docker_enabled:
        print("⚠️ Docker must be set up before Vercel — skipping Vercel setup")
        return

    docker_interpreter.setup_vercel(vercel_token)
    vercel_enabled = True

    # Map Vercel tools
    for tool in docker_interpreter.get_vercel_tools():
        tool_to_server_map[tool["name"]] = "vercel"


async def _connect_server(server_name: str, server_params: StdioServerParameters):
    """Internal helper to connect to any MCP server"""
    global mcp_servers, tool_to_server_map, exit_stack

    # Create and enter the stdio_client context manager
    stdio_context = stdio_client(server_params)
    read_stream, write_stream = await stdio_context.__aenter__()
    exit_stack.append(('stdio_context', stdio_context))

    # Create and enter the ClientSession context manager
    session_context = ClientSession(read_stream, write_stream)
    session = await session_context.__aenter__()
    exit_stack.append(('session_context', session_context))

    await session.initialize()

    mcp_servers[server_name] = {
        'session': session,
        'session_context': session_context,
        'stdio_context': stdio_context
    }

    tools_list = await session.list_tools()
    for tool in tools_list.tools:
        tool_to_server_map[tool.name] = server_name

    print(f" {server_name} server connected ({len(tools_list.tools)} tools)")


async def get_all_tools_for_claude() -> List[Dict[str, Any]]:
    """Get all tools formatted for Claude"""
    all_tools = []

    # Get MCP server tools
    for server_name, server_info in mcp_servers.items():
        session = server_info['session']
        tools_list = await session.list_tools()

        for tool in tools_list.tools:
            all_tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            })

    # Add Docker tools
    if docker_enabled:
        all_tools.extend(docker_interpreter.get_docker_tools())

    # Add Vercel tools
    if vercel_enabled:
        all_tools.extend(docker_interpreter.get_vercel_tools())

    return all_tools


async def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> Any:
    """Execute a tool by routing to correct server"""
    server_name = tool_to_server_map.get(tool_name)

    if not server_name:
        raise ValueError(f"Tool '{tool_name}' not found")

    # Route to Docker
    if server_name == "docker":
        return execute_docker_tool(tool_name, tool_input)

    # Route to Vercel
    if server_name == "vercel":
        return execute_vercel_tool(tool_name, tool_input)

    # Route to MCP server
    session = mcp_servers[server_name]['session']
    print(f" Executing {tool_name} on {server_name} server")
    result = await session.call_tool(tool_name, tool_input)

    return result


def execute_docker_tool(tool_name: str, tool_input: Dict[str, Any]):
    """Execute Docker tool (synchronous)"""
    if tool_name == "execute_python":
        result = docker_interpreter.execute_python(tool_input["code"])
    elif tool_name == "execute_bash":
        result = docker_interpreter.execute_bash(tool_input["command"])
    elif tool_name == "write_file":
        content = docker_interpreter.write_file(tool_input["path"], tool_input["content"])
        result = {"content": content}
    elif tool_name == "read_file":
        content = docker_interpreter.read_file(tool_input["path"])
        result = {"content": content}
    elif tool_name == "list_local_files":
        files = docker_interpreter.list_local_files()
        result = {"content": files}
    elif tool_name == "sync_files":
        content = docker_interpreter.sync_all_files_from_container()
        result = {"content": content}
    else:
        raise ValueError(f"Unknown Docker tool: {tool_name}")

    # Convert to MCP-like format
    class Result:
        def __init__(self, content):
            self.content = [type('obj', (object,), {'text': content})]

    return Result(result["content"])


def execute_vercel_tool(tool_name: str, tool_input: Dict[str, Any]):
    """Execute Vercel CLI tool (runs inside Docker)"""
    if tool_name == "vercel_deploy":
        result = docker_interpreter.vercel_deploy(
            project_dir=tool_input.get("project_dir", "/workspace"),
            prod=tool_input.get("prod", False)
        )
    elif tool_name == "vercel_list_projects":
        result = docker_interpreter.vercel_list_projects()
    elif tool_name == "vercel_list_deployments":
        result = docker_interpreter.vercel_list_deployments(
            project_name=tool_input.get("project_name")
        )
    elif tool_name == "vercel_logs":
        result = docker_interpreter.vercel_logs(tool_input["deployment_url"])
    elif tool_name == "vercel_inspect":
        result = docker_interpreter.vercel_inspect(tool_input["deployment_url"])
    elif tool_name == "vercel_env_add":
        result = docker_interpreter.vercel_env_add(
            key=tool_input["key"],
            value=tool_input["value"],
            environment=tool_input.get("environment", "production"),
            project_name=tool_input.get("project_name")
        )
    else:
        raise ValueError(f"Unknown Vercel tool: {tool_name}")

    # Convert to MCP-like format
    class Result:
        def __init__(self, content):
            self.content = [type('obj', (object,), {'text': content})]

    return Result(result["content"])


def get_tools_summary() -> Dict[str, List[str]]:
    """Get summary of available tools"""
    summary = {}
    for tool_name, server_name in tool_to_server_map.items():
        if server_name not in summary:
            summary[server_name] = []
        summary[server_name].append(tool_name)
    return summary


async def close_all_servers():
    """Close all connections"""
    global mcp_servers, tool_to_server_map, exit_stack, docker_enabled

    print("\n🔌 Closing connections...")

    # Close MCP servers in reverse order
    for context_type, context_manager in reversed(exit_stack):
        try:
            await context_manager.__aexit__(None, None, None)
        except Exception as e:
            print(f"Warning: Error closing {context_type}: {e}")

    # Close Docker
    if docker_enabled:
        docker_interpreter.close_docker()
        docker_enabled = False

    exit_stack.clear()
    mcp_servers.clear()
    tool_to_server_map.clear()