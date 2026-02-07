"""
Test script for Docker-based code interpreter
Run this to verify Docker setup is working
"""
import sys
import os

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')  # Set console to UTF-8
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import docker_interpreter

def test_docker():
    print("=" * 60)
    print("Testing Docker Code Interpreter")
    print("=" * 60)

    # Connect to Docker
    print("\n1. Connecting to Docker...")
    try:
        docker_interpreter.connect_docker("./workspace")
        print("[OK] Docker connected successfully")
    except Exception as e:
        print(f"[FAILED] Failed to connect: {e}")
        return

    # Test Python execution
    print("\n2. Testing Python execution...")
    try:
        result = docker_interpreter.execute_python("print('Hello from Docker!')")
        print(f"[OK] Python execution result: {result['content']}")
    except Exception as e:
        print(f"[FAILED] Python execution failed: {e}")

    # Test Bash execution
    print("\n3. Testing Bash execution...")
    try:
        result = docker_interpreter.execute_bash("echo 'Bash works!' && pwd")
        print(f"[OK] Bash execution result: {result['content']}")
    except Exception as e:
        print(f"[FAILED] Bash execution failed: {e}")

    # Test file writing
    print("\n4. Testing file write...")
    try:
        result = docker_interpreter.write_file("test.txt", "Hello Docker World!")
        print(f"[OK] File write result: {result}")
    except Exception as e:
        print(f"[FAILED] File write failed: {e}")

    # Test file reading
    print("\n5. Testing file read...")
    try:
        content = docker_interpreter.read_file("test.txt")
        print(f"[OK] File read result: {content}")
    except Exception as e:
        print(f"[FAILED] File read failed: {e}")

    # Test listing files
    print("\n6. Testing list files...")
    try:
        files = docker_interpreter.list_local_files()
        print(f"[OK] Files in workspace:\n{files}")
    except Exception as e:
        print(f"[FAILED] List files failed: {e}")

    # Test Python with file creation
    print("\n7. Testing Python with file creation...")
    try:
        python_code = """
with open('python_test.txt', 'w') as f:
    f.write('Created by Python in Docker!')
print('File created successfully')
"""
        result = docker_interpreter.execute_python(python_code)
        print(f"[OK] Python file creation: {result['content']}")
    except Exception as e:
        print(f"[FAILED] Python file creation failed: {e}")

    # Close Docker
    print("\n8. Closing Docker...")
    try:
        docker_interpreter.close_docker()
        print("[OK] Docker closed successfully")
    except Exception as e:
        print(f"[FAILED] Failed to close Docker: {e}")

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print(f"\n[FILES] Check your workspace at: {docker_interpreter.get_current_project_path()}")

if __name__ == "__main__":
    test_docker()