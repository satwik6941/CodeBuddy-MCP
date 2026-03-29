# CodeBuddy MCP

An AI-powered development assistant that uses the **Model Context Protocol (MCP)** to connect LLMs with real-world developer tools. CodeBuddy can write and execute code, manage GitHub repositories, and deploy projects to Vercel and Render -- all through a conversational interface.

## Features

- **Multi-LLM Support** -- Choose between Anthropic (Claude) or OpenRouter (GPT-4o, Gemini, and more)
- **Sandboxed Code Execution** -- Run Python and Bash safely inside Docker containers
- **GitHub Integration** -- Create repos, manage issues/PRs, search code, and push files via MCP
- **Vercel Deployment** -- Deploy projects, manage environment variables, and inspect deployments
- **Render Deployment** -- Deploy and manage cloud services on Render via MCP
- **Multi-Turn Conversations** -- Maintains full conversation history for context-aware assistance
- **Workspace Management** -- Timestamped session directories keep projects organized

## Architecture

```
User Input
    |
    v
 main.py ──> API Provider Selection
    |
    v
 llm.py ──> LLM Communication (Anthropic / OpenRouter)
    |              |
    |         Tool Calls
    v              v
 mcp_connections.py ──> Tool Router
    |         |              |
    v         v              v
 GitHub    Render     docker_interpreter.py
  MCP       MCP              |
 Server    Server      Docker Container
                        (Python, Bash,
                         Vercel CLI)
```

## Project Structure

| File | Description |
|------|-------------|
| `main.py` | Entry point -- handles user input, API selection, and the interactive loop |
| `llm.py` | LLM handler for Anthropic and OpenRouter APIs with tool-calling support |
| `mcp_connections.py` | MCP connection manager -- routes tool calls to GitHub, Render, or Docker |
| `docker_interpreter.py` | Docker container manager for sandboxed code execution and file ops |
| `custom_server.py` | FastMCP server template for defining custom tools |
| `Dockerfile` | Container image with Python 3.12, Node.js 22, and Vercel CLI |
| `test_docker.py` | Verification script for testing the Docker setup |

## Prerequisites

- Python 3.12+
- Docker Desktop (running)
- Node.js 20+
- API keys for the services you want to use

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/satwik6941/CodeBuddy-MCP.git
   cd CodeBuddy-MCP
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   Create a `.env` file in the project root:
   ```env
   GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
   CLAUDE_API_KEY=sk-ant-api03-your_key_here
   OPENROUTER_API_KEY=sk-or-v1-your_key_here     # Optional
   RENDER_API_KEY=rnd_your_key_here
   VERCEL_TOKEN=your_vercel_token_here
   ```

4. **Build the Docker image**
   ```bash
   docker build -t codebuddy-mcp .
   ```

5. **Verify Docker setup** (optional)
   ```bash
   python test_docker.py
   ```

## Usage

```bash
python main.py
```

On launch, you will:
1. Describe your problem statement or task
2. Select an API provider (Anthropic or OpenRouter)
3. If OpenRouter, choose a model from the list or enter a custom one
4. Enter interactive mode where you can chat with the AI assistant

Type `exit` to quit the session.

### Example Workflows

**Create and deploy a web app:**
> "Build a simple Express API with a /health endpoint and deploy it to Vercel"

**Analyze data:**
> "Read my CSV file, compute summary statistics, and generate a bar chart"

**Fix a bug:**
> "Clone my repo, find why the login endpoint returns 500, and push a fix"

## Available Tools

### GitHub (via MCP)
Create/manage repositories, issues, pull requests, branches, and files. Search code across repos.

### Docker (Code Execution)
| Tool | Description |
|------|-------------|
| `execute_python` | Run Python code in a sandboxed container |
| `execute_bash` | Run Bash commands in the container |
| `write_file` | Create or write files in the workspace |
| `read_file` | Read file contents from the workspace |
| `list_local_files` | List files in the workspace directory |
| `sync_files` | Sync container files to local workspace |

### Vercel (Deployment)
| Tool | Description |
|------|-------------|
| `vercel_deploy` | Deploy a project to Vercel |
| `vercel_list_projects` | List all Vercel projects |
| `vercel_list_deployments` | List deployments for a project |
| `vercel_logs` | View deployment logs |
| `vercel_inspect` | Inspect deployment details |
| `vercel_env_add` | Add environment variables |

### Render (via MCP)
Deploy services, manage environment variables, view logs, and scale services.

### Custom Tools
Define your own tools in `custom_server.py` using the FastMCP framework.

## Tech Stack

- **Python 3.12** -- Core language
- **MCP (Model Context Protocol)** -- Tool integration framework
- **Anthropic SDK** -- Claude API access
- **OpenAI SDK** -- OpenRouter compatibility
- **Docker** -- Sandboxed code execution
- **Vercel CLI** -- Cloud deployment
- **FastMCP** -- Custom MCP server framework

## License

This project is open source. See the repository for license details.