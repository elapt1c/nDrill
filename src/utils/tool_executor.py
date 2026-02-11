# src/utils/tool_executor.py
import subprocess
import os
import json
import uuid
import shlex

class ToolExecutor:
    def __init__(self):
        self.agent_tools_image = "ndrill-agent-tools"
        self.container_name = f"ndrill-session-{uuid.uuid4().hex[:8]}"
        self._is_container_running = False
        print("ToolExecutor: Initializing.")

        if not self._docker_image_exists(self.agent_tools_image):
            print(f"ToolExecutor: Docker image '{self.agent_tools_image}' not found, building now.")
            self.build_agent_tools_image()
        else:
            print(f"ToolExecutor: Docker image '{self.agent_tools_image}' already exists.")

    def _docker_command(self, cmd):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise e

    def _docker_image_exists(self, image_name):
        try:
            output = self._docker_command(["docker", "images", "-q", image_name])
            return len(output) > 0
        except:
            return False

    def build_agent_tools_image(self):
        print(f"ToolExecutor: Building Docker image '{self.agent_tools_image}'...")
        try:
            subprocess.run(["docker", "build", "-t", self.agent_tools_image, "-f", "docker/Dockerfile.agent_tools", "."], check=True)
            return True
        except Exception as e:
            print(f"ToolExecutor: Error building image: {e}")
            return False

    def _ensure_container_running(self):
        if not self._is_container_running:
            try:
                print(f"ToolExecutor: Starting session container '{self.container_name}'...")
                subprocess.run([
                    "docker", "run", "-d",
                    "--name", self.container_name,
                    "--network", "bridge",
                    "--memory", "1g",
                    "--cpus", "1.0",
                    self.agent_tools_image,
                    "sleep", "infinity"
                ], check=True)
                self._is_container_running = True
            except Exception as e:
                print(f"ToolExecutor: Failed to start container: {e}")

    def write_file_to_container(self, file_content, container_path):
        self._ensure_container_running()
        try:
            process = subprocess.Popen(
                ["docker", "exec", "-i", self.container_name, "sh", "-c", f"cat > {container_path}"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=file_content)
            if process.returncode != 0:
                print(f"ToolExecutor: Error writing file to container: {stderr}")
                return False
            return True
        except Exception as e:
            print(f"ToolExecutor: Exception writing file: {e}")
            return False

    def execute_tool(self, tool_name, args, target_url):
        self._ensure_container_running()
        
        if isinstance(args, str):
            args = shlex.split(args)
        
        command = [tool_name] + args
        
        try:
            exec_cmd = ["docker", "exec", self.container_name] + command
            print(f"ToolExecutor: [EXEC] {' '.join(exec_cmd)}")
            result = subprocess.run(exec_cmd, capture_output=True, text=True, check=True, timeout=600)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error: Tool '{tool_name}' failed with code {e.returncode}\nStdout: {e.stdout}\nStderr: {e.stderr}"
        except Exception as e:
            return f"Error: {e}"

    def cleanup(self):
        if self._is_container_running:
            print(f"ToolExecutor: Cleaning up container '{self.container_name}'...")
            subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True)
            self._is_container_running = False
