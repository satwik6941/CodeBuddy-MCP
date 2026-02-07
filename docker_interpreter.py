import subprocess
import json
from typing import Optional, Dict, Any
import os
from datetime import datetime
import shlex

# Global container information
container_id: Optional[str] = None
container_name: Optional[str] = None
local_workspace_path = None
current_project_path = None


def _run_docker_command(command: list, check=True) -> subprocess.CompletedProcess:
    """Run a docker CLI command"""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=check,
            encoding='utf-8',
            errors='replace'
        )
        return result
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Docker command failed: {e.stderr}")


def connect_docker(workspace_path: str = "./workspace", image: str = "python:3.11-slim"):
    """Connect to Docker and create a container for code execution"""
    global container_id, container_name, local_workspace_path, current_project_path

    print("🐳 Starting Docker container...")

    # Check if Docker is running
    try:
        result = _run_docker_command(["docker", "info"], check=False)
        if result.returncode != 0:
            raise ConnectionError("Docker is not running")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to Docker. Is Docker Desktop running? Error: {e}")

    # Setup local workspace directory structure
    local_workspace_path = os.path.abspath(workspace_path)
    projects_dir = os.path.join(local_workspace_path, "projects")

    # Create directories if they don't exist
    os.makedirs(projects_dir, exist_ok=True)

    # Create a new project folder for this session
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    current_project_path = os.path.join(projects_dir, f"session_{timestamp}")
    os.makedirs(current_project_path, exist_ok=True)

    # Create a 'current' directory for easy access
    current_link = os.path.join(projects_dir, "current")
    if os.path.exists(current_link):
        if os.path.islink(current_link):
            os.unlink(current_link)
        elif os.path.isdir(current_link):
            import shutil
            shutil.rmtree(current_link)

    # Copy directory instead of symlink (Windows-compatible)
    import shutil
    shutil.copytree(current_project_path, current_link, dirs_exist_ok=True)

    # Create container name
    container_name = f"code_interpreter_{timestamp}"

    try:
        # Pull the image if not available
        print(f"📦 Checking for image: {image}")
        result = _run_docker_command(["docker", "images", "-q", image], check=False)
        if not result.stdout.strip():
            print(f"📥 Pulling image: {image}")
            _run_docker_command(["docker", "pull", image])

        # Create and start container using Docker CLI
        # Convert Windows path to proper format for Docker
        workspace_mount = current_project_path.replace('\\', '/')

        # Run container in detached mode with volume mount
        result = _run_docker_command([
            "docker", "run",
            "-d",  # Detached mode
            "--name", container_name,
            "-v", f"{workspace_mount}:/workspace",
            "-w", "/workspace",
            "--entrypoint", "/bin/sh",
            image,
            "-c", "apt-get update -qq && apt-get install -y -qq curl wget git vim nano > /dev/null 2>&1; tail -f /dev/null"
        ])

        container_id = result.stdout.strip()[:12]  # Get short ID
        print(f"✅ Docker container started (ID: {container_id})")
        print(f"📁 Local workspace: {local_workspace_path}")
        print(f"📂 Current project: {current_project_path}")
        print(f"🔗 Quick access: {current_link}")

        # Wait for container to be ready
        import time
        time.sleep(2)

    except Exception as e:
        raise RuntimeError(f"Failed to create Docker container: {e}")


def get_current_project_path() -> str:
    """Get the current project directory path"""
    if not current_project_path:
        raise ValueError("Docker not connected - no project path available")
    return current_project_path


def execute_code(language: str, code: str) -> Dict[str, Any]:
    """Execute code in Docker container"""
    global container_name

    if not container_name:
        raise ValueError("Docker container not connected")

    print(f"🔧 Executing {language} code in Docker")
    print(f"Code:\n{code}\n")

    # Determine the command based on language
    if language.lower() in ["python", "py"]:
        # Escape the code properly for shell
        cmd = ["docker", "exec", container_name, "python3", "-c", code]
    elif language.lower() in ["bash", "sh", "shell"]:
        cmd = ["docker", "exec", container_name, "/bin/bash", "-c", code]
    elif language.lower() in ["javascript", "js", "node"]:
        # Install node if not present
        _run_docker_command([
            "docker", "exec", container_name, "/bin/bash", "-c",
            "which node || (curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && apt-get install -y nodejs)"
        ], check=False)
        cmd = ["docker", "exec", container_name, "node", "-e", code]
    else:
        return {
            "content": f"Unsupported language: {language}",
            "details": {"success": False, "error": f"Language {language} not supported"}
        }

    try:
        # Execute the command
        result = _run_docker_command(cmd, check=False)

        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr

        # Build result
        result_data = {
            "success": exit_code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "error": None if exit_code == 0 else f"Exit code: {exit_code}"
        }

        # Format result text
        result_text = ""
        if result_data["stdout"]:
            result_text += f"Output:\n{result_data['stdout']}"
        if result_data["stderr"]:
            result_text += f"\nErrors:\n{result_data['stderr']}"
        if result_data["error"]:
            result_text += f"\nError: {result_data['error']}"

        if not result_text:
            result_text = "Code executed successfully (no output)"

        print(f"✅ Result:\n{result_text}\n")

        return {
            "content": result_text,
            "details": result_data
        }

    except Exception as e:
        error_msg = f"Execution error: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            "content": error_msg,
            "details": {"success": False, "error": str(e)}
        }


def execute_bash(command: str) -> Dict[str, Any]:
    """Execute bash command in Docker"""
    return execute_code("bash", command)


def execute_python(code: str) -> Dict[str, Any]:
    """Execute Python code in Docker"""
    return execute_code("python", code)


def read_file(path: str) -> str:
    """Read file from Docker container workspace"""
    global container_name, current_project_path

    if not container_name:
        raise ValueError("Docker container not connected")

    print(f"📖 Reading file: {path}")

    try:
        # Try local path first (mounted volume)
        local_file_path = os.path.join(current_project_path, os.path.basename(path))

        if os.path.exists(local_file_path):
            with open(local_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"✅ File read successfully from local workspace")
            return content

        # If not in local, try reading from container
        container_path = f"/workspace/{os.path.basename(path)}"
        result = _run_docker_command(["docker", "exec", container_name, "cat", container_path], check=False)

        if result.returncode == 0:
            content = result.stdout
            print(f"✅ File read successfully from container")
            return content
        else:
            raise FileNotFoundError(f"File not found: {path}")

    except Exception as e:
        print(f"❌ Error reading file: {e}")
        raise


def write_file(path: str, content: str) -> str:
    """Write file to Docker container workspace"""
    global container_name, current_project_path

    if not container_name:
        raise ValueError("Docker container not connected")

    print(f"✍️ Writing to file: {path}")

    try:
        # Get just the filename
        filename = os.path.basename(path)
        local_file_path = os.path.join(current_project_path, filename)

        # Write to local workspace (automatically syncs to container via volume mount)
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

        with open(local_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ File written to: {local_file_path}")

        # Update the 'current' directory copy
        current_link = os.path.join(os.path.dirname(current_project_path), "current")
        current_link_file = os.path.join(current_link, filename)
        os.makedirs(os.path.dirname(current_link_file), exist_ok=True)
        with open(current_link_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return f"File {path} created successfully at: {local_file_path}"
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        raise


def write_file_to_directory(filename: str, content: str, subdirectory: str = None) -> str:
    """Write file to a specific subdirectory in the project"""
    global container_name, current_project_path

    if not container_name:
        raise ValueError("Docker container not connected")

    # Determine target directory
    if subdirectory:
        target_dir = os.path.join(current_project_path, subdirectory)
    else:
        target_dir = current_project_path

    # Create directory if it doesn't exist
    os.makedirs(target_dir, exist_ok=True)

    # Full local path
    local_file_path = os.path.join(target_dir, filename)

    print(f"✍️ Writing to directory: {subdirectory or 'root'}")
    print(f"📄 Full path: {local_file_path}")

    try:
        # Write to local filesystem (syncs to container via volume)
        with open(local_file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ File saved: {local_file_path}")

        return f"File created: {local_file_path}"
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        raise


def list_files(path: str = "/workspace") -> list:
    """List files in Docker container workspace"""
    global container_name, current_project_path

    if not container_name:
        raise ValueError("Docker container not connected")

    print(f"📋 Listing files in container: {path}")

    try:
        # List from container
        result = _run_docker_command(["docker", "exec", container_name, "ls", "-la", path], check=False)

        if result.returncode == 0:
            files_output = result.stdout
            print(f"✅ Container files:\n{files_output}")

        # Also show local files
        if current_project_path and os.path.exists(current_project_path):
            local_files = os.listdir(current_project_path)
            print(f"📁 Local workspace has {len(local_files)} files: {', '.join(local_files)}")
            return local_files

        return []
    except Exception as e:
        print(f"❌ Error listing files: {e}")
        raise


def list_local_files() -> str:
    """List all files in the current local project directory"""
    if not current_project_path or not os.path.exists(current_project_path):
        return "No local project directory"

    files = []
    for root, dirs, filenames in os.walk(current_project_path):
        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(root, filename), current_project_path)
            files.append(rel_path)

    return "\n".join(files) if files else "No files in local workspace"


def sync_all_files_from_container() -> str:
    """Sync all files from Docker container to local workspace"""
    global container_name, current_project_path

    if not container_name:
        raise ValueError("Docker container not connected")

    print("🔄 Syncing files from Docker container to local workspace...")

    # Since we're using volume mounts, files are already synced
    # But let's verify and copy any files that might only exist in container

    try:
        # List all files in container workspace
        result = _run_docker_command(["docker", "exec", container_name, "find", "/workspace", "-type", "f"], check=False)

        if result.returncode != 0:
            return "No files to sync"

        files = result.stdout.strip().split('\n')
        synced_count = 0

        for file_path in files:
            if not file_path or file_path == '/workspace':
                continue

            # Get relative path
            rel_path = file_path.replace('/workspace/', '')
            local_path = os.path.join(current_project_path, rel_path)

            # Skip if already exists locally
            if os.path.exists(local_path):
                continue

            # Copy from container using docker cp
            try:
                _run_docker_command(["docker", "cp", f"{container_name}:{file_path}", local_path])
                synced_count += 1
                print(f"  ✅ Synced: {rel_path}")
            except Exception as e:
                print(f"  ⚠️ Skipped {rel_path}: {e}")

        return f"Synced {synced_count} files to {current_project_path}"
    except Exception as e:
        print(f"❌ Error syncing files: {e}")
        return f"Error syncing files: {e}"


def close_docker():
    """Stop and remove Docker container"""
    global container_name, container_id

    if container_name:
        print("\n🔄 Syncing files before closing...")
        try:
            sync_all_files_from_container()
        except Exception as e:
            print(f"⚠️ Warning: Could not sync all files: {e}")

        print("🛑 Stopping Docker container...")
        try:
            # Stop container
            _run_docker_command(["docker", "stop", container_name], check=False)
            # Remove container
            _run_docker_command(["docker", "rm", container_name], check=False)
            print("✅ Docker container stopped and removed")
        except Exception as e:
            print(f"⚠️ Warning: Error stopping container: {e}")

        container_name = None
        container_id = None

        if current_project_path:
            print(f"\n💾 Your files are saved in: {current_project_path}")
            print(f"🔗 Quick access at: {os.path.join(os.path.dirname(current_project_path), 'current')}")


def get_docker_tools() -> list:
    """Get Docker code execution tools in Claude format"""
    return [
        {
            "name": "execute_python",
            "description": "Execute Python code in a Docker container. Files created are automatically saved to local workspace.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute"
                    }
                },
                "required": ["code"]
            }
        },
        {
            "name": "execute_bash",
            "description": "Execute bash commands in a Docker container.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Bash command to execute"
                    }
                },
                "required": ["command"]
            }
        },
        {
            "name": "write_file",
            "description": "Write content to a file. File is saved in Docker container workspace and local directory.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File name or path"
                    },
                    "content": {
                        "type": "string",
                        "description": "File content"
                    }
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "read_file",
            "description": "Read content from a file in the container workspace",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "list_local_files",
            "description": "List all files in the local workspace directory",
            "input_schema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "sync_files",
            "description": "Sync all files from Docker container to local workspace",
            "input_schema": {
                "type": "object",
                "properties": {}
            }
        }
    ]