# claude_handler.py
from anthropic import Anthropic
from openai import OpenAI
from typing import List, Dict, Any, Union
import json
import mcp_connections

# Global conversation history and API type
conversation_history = []
api_type = None  # 'anthropic' or 'openrouter'

# System prompt - ENHANCED
SYSTEM_PROMPT = """You are an AI Development Assistant that helps developers with their workflow.

You have access to:
- GitHub tools: Create repos, issues, PRs, manage files, search code, clone repositories
- Docker Code Execution: Execute Python/Bash code in a sandboxed environment, create/read/write files, install packages
- Render tools: Deploy and manage services on Render
- Vercel tools: Deploy projects to Vercel, list projects/deployments, view logs, manage env vars

Your capabilities:
1. Code Management: Clone repos, create branches, commit changes, push code
2. Issue Tracking: Create/update issues, link to PRs
3. Code Execution: Run Python scripts, execute bash commands, install packages
4. File Operations: Create, read, write, list files in the sandbox
5. Data Processing: Install and use libraries like pandas, numpy, matplotlib
6. Testing: Run tests, linters, formatters
7. Vercel Deployment: Deploy projects (preview/production), list projects, view deployment logs, inspect deployments, manage environment variables
8. Render Deployment: Deploy and manage services on Render

CRITICAL RULES FOR TASK COMPLETION:
1. ALWAYS complete the ENTIRE task before responding with just text
2. If asked to "create and run" - do BOTH: create file, THEN execute it
3. If asked to "install and use" - do BOTH: install package, THEN use it
4. If asked to "analyze data" - download, process, AND show results
5. Use multiple tools in sequence to complete multi-step tasks
6. After each tool use, check: "Is the task fully complete?" If NO, use more tools
7. Only respond with text when the ENTIRE task is done

Examples of CORRECT behavior:
- User: "Create hello.py and run it"
  → write_file (create hello.py)
  → execute_python (run hello.py)
  → Respond: "Created and ran hello.py. Output: Hello World"

- User: "Install requests and fetch data from an API"
  → execute_bash (pip install requests)
  → execute_python (script that uses requests)
  → Respond: "Installed requests and fetched data: [results]"

Examples of WRONG behavior:
- User: "Create hello.py and run it"
  → write_file (create hello.py)
  → Respond: "I've created hello.py"  WRONG - didn't run it!

Guidelines:
- Break down tasks into steps
- Execute ALL steps before giving final response
- Always show outputs from code execution
- Handle errors gracefully and suggest fixes
- Confirm destructive operations before executing"""


def init_claude(api_key: str) -> Anthropic:
    """Initialize Claude client with Anthropic API"""
    global api_type
    api_type = 'anthropic'
    return Anthropic(api_key=api_key)


def init_openrouter(api_key: str, site_url: str = "http://localhost:3000", site_name: str = "CodeBuddy MCP") -> OpenAI:
    """Initialize OpenRouter client using OpenAI library"""
    global api_type
    api_type = 'openrouter'
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": site_url,
            "X-Title": site_name,
        }
    )
    return client


async def send_message(
    client: Union[Anthropic, OpenAI],
    user_message: str,
    max_tool_rounds: int = 20,
    model: str = None
) -> str:
    """Send message to LLM and handle tool calls until task is complete"""
    global conversation_history, api_type

    print(f"\n👤 You: {user_message}\n")

    # Add user message to history
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

    # Get available tools from MCP and E2B
    tools = await mcp_connections.get_all_tools_for_claude()

    # Track tool rounds to prevent infinite loops
    tool_round = 0

    # Set default model based on API type
    if model is None:
        if api_type == 'anthropic':
            model = "claude-sonnet-4-20250514"
        else:  # openrouter
            model = "anthropic/claude-sonnet-4-20250514"

    # Call LLM based on API type
    if api_type == 'anthropic':
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=conversation_history
        )
    else:  # openrouter
        # Convert conversation history to OpenAI format
        openai_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        openai_messages.extend(conversation_history)

        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            tools=convert_tools_to_openai_format(tools) if tools else None,
            messages=openai_messages
        )
    
    # Handle tool use loop - KEEP GOING UNTIL LLM STOPS
    should_continue = (api_type == 'anthropic' and response.stop_reason == "tool_use") or \
                     (api_type == 'openrouter' and response.choices[0].finish_reason == "tool_calls")

    while should_continue:
        tool_round += 1

        # Safety check: prevent infinite loops
        if tool_round > max_tool_rounds:
            print(f" Warning: Reached maximum tool rounds ({max_tool_rounds})")
            print(" Forcing completion to prevent infinite loop")
            break

        print(f" AI is using tools... (Round {tool_round})\n")

        assistant_content = []
        tool_results = []

        if api_type == 'anthropic':
            # Process Anthropic response
            for content_block in response.content:
                if content_block.type == "text":
                    if content_block.text.strip():
                        print(f"💭 AI: {content_block.text}\n")
                    assistant_content.append(content_block)

                elif content_block.type == "tool_use":
                    assistant_content.append(content_block)

                    tool_name = content_block.name
                    tool_input = content_block.input

                    print(f" Tool #{len(tool_results)+1}: {tool_name}")
                    print(f" Input: {json.dumps(tool_input, indent=2)}")

                    try:
                        result = await mcp_connections.execute_tool(tool_name, tool_input)
                        result_text = extract_result_text(result)
                        display_text = result_text[:500] + "..." if len(result_text) > 500 else result_text
                        print(f" Result: {display_text}\n")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": result_text
                        })
                    except Exception as e:
                        error_msg = str(e)
                        print(f" Error: {error_msg}\n")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": f"Error executing tool: {error_msg}",
                            "is_error": True
                        })

            # Add to conversation history
            conversation_history.append({
                "role": "assistant",
                "content": assistant_content
            })

            conversation_history.append({
                "role": "user",
                "content": tool_results
            })

            # Continue conversation
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=conversation_history
            )

            should_continue = response.stop_reason == "tool_use"

        else:  # openrouter
            # Process OpenRouter/OpenAI response
            message = response.choices[0].message

            if message.content:
                print(f"💭 AI: {message.content}\n")

            # Process tool calls (check if tool_calls exists and is not None)
            if not message.tool_calls:
                print(" Warning: No tool calls found in response")
                break

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                # Handle arguments - could be string or dict
                if isinstance(tool_call.function.arguments, str):
                    tool_input = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                else:
                    tool_input = tool_call.function.arguments or {}

                print(f" Tool #{len(tool_results)+1}: {tool_name}")
                print(f" Input: {json.dumps(tool_input, indent=2)}")

                try:
                    result = await mcp_connections.execute_tool(tool_name, tool_input)
                    result_text = extract_result_text(result)
                    display_text = result_text[:500] + "..." if len(result_text) > 500 else result_text
                    print(f" Result: {display_text}\n")

                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": result_text
                    })
                except Exception as e:
                    error_msg = str(e)
                    print(f" Error: {error_msg}\n")
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": f"Error executing tool: {error_msg}"
                    })

            # Add to conversation history (OpenAI format)
            assistant_msg = {
                "role": "assistant",
                "content": message.content
            }

            if message.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]

            conversation_history.append(assistant_msg)

            # Add tool results
            conversation_history.extend(tool_results)

            # Continue conversation
            openai_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            openai_messages.extend(conversation_history)

            response = client.chat.completions.create(
                model=model,
                max_tokens=4096,
                tools=convert_tools_to_openai_format(tools) if tools else None,
                messages=openai_messages
            )

            should_continue = response.choices[0].finish_reason == "tool_calls"

        # Show progress
        print(f"{'='*60}")
        print(f"Completed tool round {tool_round}")
        print(f"AI's decision: {response.stop_reason if api_type == 'anthropic' else response.choices[0].finish_reason}")
        print(f"{'='*60}\n")
    
    # Extract final response
    final_response = ""
    if api_type == 'anthropic':
        for content_block in response.content:
            if hasattr(content_block, "text"):
                final_response += content_block.text

        # Add to history
        conversation_history.append({
            "role": "assistant",
            "content": response.content
        })
    else:  # openrouter
        final_response = response.choices[0].message.content or ""

        # Add to history
        conversation_history.append({
            "role": "assistant",
            "content": final_response
        })

    # Show completion summary
    if tool_round > 0:
        print(f" Task completed after {tool_round} tool rounds\n")

    return final_response


def convert_tools_to_openai_format(anthropic_tools: List[Dict]) -> List[Dict]:
    """Convert Anthropic tool format to OpenAI function calling format"""
    openai_tools = []
    for tool in anthropic_tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"]
            }
        }
        openai_tools.append(openai_tool)
    return openai_tools


def extract_result_text(result: Any) -> str:
    """Extract text from MCP or E2B result"""
    # Handle MCP result format
    if hasattr(result, 'content'):
        if isinstance(result.content, list):
            text_parts = []
            for item in result.content:
                if hasattr(item, 'text'):
                    text_parts.append(str(item.text))
                else:
                    text_parts.append(str(item))
            return "\n".join(text_parts)
        else:
            return str(result.content)
    
    # Handle direct string
    if isinstance(result, str):
        return result
    
    # Handle dict format (from E2B wrapper)
    if isinstance(result, dict) and 'content' in result:
        return str(result['content'])
    
    # Fallback
    return str(result)


def clear_history():
    """Clear conversation history"""
    global conversation_history
    conversation_history = []
    print(" Conversation history cleared")


def get_conversation_length() -> int:
    """Get number of messages in conversation"""
    return len(conversation_history)


def print_conversation_stats():
    """Print statistics about current conversation"""
    total_messages = len(conversation_history)
    user_messages = sum(1 for msg in conversation_history if msg['role'] == 'user')
    assistant_messages = sum(1 for msg in conversation_history if msg['role'] == 'assistant')
    
    # Count tool uses
    tool_uses = 0
    for msg in conversation_history:
        if msg['role'] == 'assistant' and isinstance(msg.get('content'), list):
            tool_uses += sum(1 for item in msg['content'] 
                           if hasattr(item, 'type') and item.type == 'tool_use')
    
    print(f"\n Conversation Stats:")
    print(f"   Total messages: {total_messages}")
    print(f"   User messages: {user_messages}")
    print(f"   Assistant messages: {assistant_messages}")
    print(f"   Tool uses: {tool_uses}")


def truncate_history(keep_last_n: int):
    """Keep only the last n messages in history to manage token usage"""
    global conversation_history
    
    if len(conversation_history) > keep_last_n:
        removed = len(conversation_history) - keep_last_n
        conversation_history = conversation_history[-keep_last_n:]
        print(f" Truncated history: removed {removed} old messages, kept last {keep_last_n}")