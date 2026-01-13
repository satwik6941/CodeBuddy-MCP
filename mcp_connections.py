# mcp_connections.py
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Dict, Any, List
import code_interpreter

# Global state
mcp_servers = {}
tool_to_server_map = {}
exit_stack = []
e2b_enabled = False


async def connect_github_server(github_token: str):
    """Connect to GitHub MCP server"""
    print("🔌 Connecting to GitHub server...")
    
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": github_token}
    )
    
    await _connect_server("github", server_params)


def setup_e2b(api_key: str):
    """Setup E2B sandbox (not async)"""
    global e2b_enabled
    
    code_interpreter.connect_e2b(api_key)
    e2b_enabled = True
    
    # Map E2B tools
    for tool in code_interpreter.get_e2b_tools():
        tool_to_server_map[tool["name"]] = "e2b"


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
    
    print(f"✅ {server_name} server connected ({len(tools_list.tools)} tools)")


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
    
    # Add E2B tools
    if e2b_enabled:
        all_tools.extend(code_interpreter.get_e2b_tools())
    
    return all_tools


async def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> Any:
    """Execute a tool by routing to correct server"""
    server_name = tool_to_server_map.get(tool_name)
    
    if not server_name:
        raise ValueError(f"Tool '{tool_name}' not found")
    
    # Route to E2B
    if server_name == "e2b":
        return execute_e2b_tool(tool_name, tool_input)
    
    # Route to MCP server
    session = mcp_servers[server_name]['session']
    print(f"⚙️  Executing {tool_name} on {server_name} server")
    result = await session.call_tool(tool_name, tool_input)
    
    return result


def execute_e2b_tool(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Execute E2B tool (synchronous)"""
    if tool_name == "execute_python":
        result = code_interpreter.execute_python(tool_input["code"])
    elif tool_name == "execute_bash":
        result = code_interpreter.execute_bash(tool_input["command"])
    elif tool_name == "write_file":
        content = code_interpreter.write_file(tool_input["path"], tool_input["content"])
        result = {"content": content}
    elif tool_name == "read_file":
        content = code_interpreter.read_file(tool_input["path"])
        result = {"content": content}
    elif tool_name == "list_files":
        files = code_interpreter.list_files(tool_input.get("path", "/"))
        result = {"content": "\n".join(files)}
    else:
        raise ValueError(f"Unknown E2B tool: {tool_name}")
    
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
    global mcp_servers, tool_to_server_map, exit_stack, e2b_enabled
    
    print("\n🔌 Closing connections...")
    
    # Close MCP servers in reverse order
    for context_type, context_manager in reversed(exit_stack):
        try:
            await context_manager.__aexit__(None, None, None)
        except Exception as e:
            print(f"Warning: Error closing {context_type}: {e}")
    
    # Close E2B
    if e2b_enabled:
        code_interpreter.close_e2b()
        e2b_enabled = False
    
    exit_stack.clear()
    mcp_servers.clear()
    tool_to_server_map.clear()