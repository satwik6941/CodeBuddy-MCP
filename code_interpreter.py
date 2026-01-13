# e2b_handler.py
from e2b_code_interpreter import Sandbox
from typing import Optional, Dict, Any
import os
from datetime import datetime

# Global sandbox instance
sandbox: Optional[Sandbox] = None
local_workspace_path = None
current_project_path = None


def connect_e2b(api_key: str, workspace_path: str = "./workspace"):
    """Connect to E2B sandbox and setup local workspace"""
    global sandbox, local_workspace_path, current_project_path
    
    print("🔌 Connecting to E2B sandbox...")
    
    sandbox = Sandbox(api_key=api_key)
    
    # Setup local workspace directory structure
    local_workspace_path = os.path.abspath(workspace_path)
    projects_dir = os.path.join(local_workspace_path, "projects")
    
    # Create directories if they don't exist
    os.makedirs(projects_dir, exist_ok=True)
    
    # Create a new project folder for this session
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    current_project_path = os.path.join(projects_dir, f"session_{timestamp}")
    os.makedirs(current_project_path, exist_ok=True)
    
    # Also create a 'current' symlink for easy access
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
    
    print(f"✅ E2B sandbox connected (ID: {sandbox.sandbox_id})")
    print(f"📁 Local workspace: {local_workspace_path}")
    print(f"📁 Current project: {current_project_path}")
    print(f"📁 Quick access: {current_link}")


def get_current_project_path() -> str:
    """Get the current project directory path"""
    if not current_project_path:
        raise ValueError("E2B not connected - no project path available")
    return current_project_path


def execute_code(language: str, code: str) -> Dict[str, Any]:
    """Execute code in E2B sandbox"""
    global sandbox
    
    if not sandbox:
        raise ValueError("E2B sandbox not connected")
    
    print(f"⚙️  Executing {language} code in E2B")
    print(f"📝 Code:\n{code}\n")
    
    # Execute the code
    execution = sandbox.run_code(code, language=language)
    
    # Extract results
    result = {
        "success": not execution.error,
        "stdout": "",
        "stderr": "",
        "error": None
    }
    
    # Get output
    if execution.logs:
        result["stdout"] = execution.logs.stdout
        result["stderr"] = execution.logs.stderr
    
    if execution.error:
        result["error"] = str(execution.error)
    
    # Format result text
    result_text = ""
    if result["stdout"]:
        result_text += f"Output:\n{result['stdout']}"
    if result["stderr"]:
        result_text += f"\nErrors:\n{result['stderr']}"
    if result["error"]:
        result_text += f"\nError: {result['error']}"
    
    if not result_text:
        result_text = "Code executed successfully (no output)"
    
    print(f"📤 Result:\n{result_text}\n")
    
    return {
        "content": result_text,
        "details": result
    }


def execute_bash(command: str) -> Dict[str, Any]:
    """Execute bash command in E2B"""
    return execute_code("bash", command)


def execute_python(code: str) -> Dict[str, Any]:
    """Execute Python code in E2B"""
    return execute_code("python", code)


def read_file(path: str) -> str:
    """Read file from E2B sandbox and optionally save to local"""
    global sandbox, current_project_path
    
    if not sandbox:
        raise ValueError("E2B sandbox not connected")
    
    print(f"📖 Reading file: {path}")
    
    try:
        # Read from E2B sandbox
        content = sandbox.files.read(path)
        print(f"✅ File read successfully from E2B")
        
        # Save to local workspace
        if current_project_path:
            local_file_path = os.path.join(current_project_path, os.path.basename(path))
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            
            with open(local_file_path, 'w') as f:
                f.write(content)
            
            print(f"💾 File saved locally: {local_file_path}")
        
        return content
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        raise


def write_file(path: str, content: str) -> str:
    """Write file to E2B sandbox and local workspace"""
    global sandbox, current_project_path
    
    if not sandbox:
        raise ValueError("E2B sandbox not connected")
    
    print(f"✍️  Writing to file: {path}")
    
    try:
        # Write to E2B sandbox
        sandbox.files.write(path, content)
        print(f"✅ File written to E2B sandbox: {path}")
        
        # Also save to local workspace
        if current_project_path:
            # Get just the filename (in case path has directories)
            filename = os.path.basename(path)
            local_file_path = os.path.join(current_project_path, filename)
            
            # Create parent directories if needed
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            
            with open(local_file_path, 'w') as f:
                f.write(content)
            
            print(f"💾 File saved locally: {local_file_path}")
            
            # Update the 'current' directory copy
            current_link = os.path.join(os.path.dirname(current_project_path), "current")
            current_link_file = os.path.join(current_link, filename)
            os.makedirs(os.path.dirname(current_link_file), exist_ok=True)
            with open(current_link_file, 'w') as f:
                f.write(content)
        
        return f"File {path} created successfully (E2B + Local: {local_file_path})"
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        raise


def write_file_to_directory(filename: str, content: str, subdirectory: str = None) -> str:
    """Write file to a specific subdirectory in the project"""
    global sandbox, current_project_path
    
    if not sandbox:
        raise ValueError("E2B sandbox not connected")
    
    # Determine target directory
    if subdirectory:
        target_dir = os.path.join(current_project_path, subdirectory)
    else:
        target_dir = current_project_path
    
    # Create directory if it doesn't exist
    os.makedirs(target_dir, exist_ok=True)
    
    # Full local path
    local_file_path = os.path.join(target_dir, filename)
    
    print(f"✍️  Writing to directory: {subdirectory or 'root'}")
    print(f"✍️  Full path: {local_file_path}")
    
    try:
        # Write to E2B sandbox (always in root for simplicity)
        sandbox.files.write(filename, content)
        print(f"✅ File written to E2B sandbox: {filename}")
        
        # Write to local filesystem
        with open(local_file_path, 'w') as f:
            f.write(content)
        
        print(f"💾 File saved locally: {local_file_path}")
        
        return f"File created: {local_file_path}"
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        raise


def list_files(path: str = "/") -> list:
    """List files in E2B sandbox"""
    global sandbox
    
    if not sandbox:
        raise ValueError("E2B sandbox not connected")
    
    print(f"📂 Listing files in E2B sandbox: {path}")
    
    try:
        files = sandbox.files.get_info(path)
        print(f"✅ Found {len(files)} items in E2B")
        
        # Also show local files
        if current_project_path and os.path.exists(current_project_path):
            local_files = os.listdir(current_project_path)
            print(f"📂 Local workspace has {len(local_files)} files")
        
        return files
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


def download_file_from_sandbox(sandbox_path: str, local_filename: str = None) -> str:
    """Download a specific file from E2B sandbox to local workspace"""
    global sandbox, current_project_path
    
    if not sandbox:
        raise ValueError("E2B sandbox not connected")
    
    try:
        # Read from sandbox
        content = sandbox.files.read(sandbox_path)
        
        # Determine local filename
        if not local_filename:
            local_filename = os.path.basename(sandbox_path)
        
        local_path = os.path.join(current_project_path, local_filename)
        
        # Save locally
        with open(local_path, 'w') as f:
            f.write(content)
        
        print(f"⬇️  Downloaded {sandbox_path} -> {local_path}")
        return f"File downloaded to: {local_path}"
    except Exception as e:
        print(f"❌ Error downloading file: {e}")
        raise


def sync_all_files_from_sandbox() -> str:
    """Download all files from E2B sandbox to local workspace"""
    global sandbox, current_project_path
    
    if not sandbox:
        raise ValueError("E2B sandbox not connected")
    
    print("🔄 Syncing all files from E2B sandbox to local workspace...")
    
    try:
        # List all files in sandbox
        files = sandbox.files.get_info("/")
        
        synced_count = 0
        for file_info in files:
            filename = file_info.name if hasattr(file_info, 'name') else str(file_info)
            
            try:
                content = sandbox.filesystem.read(filename)
                local_path = os.path.join(current_project_path, filename)
                
                with open(local_path, 'w') as f:
                    f.write(content)
                
                synced_count += 1
                print(f"  ✅ Synced: {filename}")
            except Exception as e:
                print(f"  ⚠️  Skipped {filename}: {e}")
        
        return f"Synced {synced_count} files to {current_project_path}"
    except Exception as e:
        print(f"❌ Error syncing files: {e}")
        raise


def close_e2b():
    """Close E2B sandbox and sync all files"""
    global sandbox
    
    if sandbox:
        print("\n🔄 Syncing files before closing...")
        try:
            sync_all_files_from_sandbox()
        except Exception as e:
            print(f"⚠️  Warning: Could not sync all files: {e}")
        
        print("🔌 Closing E2B sandbox...")
        sandbox.kill()
        sandbox = None
        print("✅ E2B sandbox closed")
        
        if current_project_path:
            print(f"\n📁 Your files are saved in: {current_project_path}")
            print(f"📁 Quick access at: {os.path.join(os.path.dirname(current_project_path), 'current')}")


def get_e2b_tools() -> list:
    """Get E2B tools in Claude format"""
    return [
        {
            "name": "execute_python",
            "description": "Execute Python code in a sandboxed environment. Files created are automatically saved to local workspace.",
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
            "description": "Execute bash commands in a sandboxed environment.",
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
            "description": "Write content to a file. File is saved both in E2B sandbox and local workspace directory.",
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
            "description": "Read content from a file in the sandbox",
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
            "description": "Sync all files from E2B sandbox to local workspace",
            "input_schema": {
                "type": "object",
                "properties": {}
            }
        }
    ]