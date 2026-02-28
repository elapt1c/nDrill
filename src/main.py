import os
import json
import argparse
import subprocess
import uuid
import time
import sys
import threading
import queue

from rich.console import Console
from rich.text import Text
from rich.panel import Panel

from agents.reconnaissance_agent import ReconnaissanceAgent
from agents.scanner_agent import ScannerAgent
from agents.exploitation_agent import ExploitationAgent
from utils.tool_executor import ToolExecutor

console = Console()

class Orchestrator:
    def __init__(self, target_url, model_id=None, user_instructions="", openrouter_key=None, event_callback=None):
        self.target_url = target_url
        self.user_instructions = user_instructions
        self.openrouter_key = openrouter_key
        self.event_callback = event_callback
        self.extra_info_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        if self.openrouter_key:
            self.model_provider = "openrouter"
            self.model_name = model_id if model_id else "google/gemini-2.0-flash-001" 
        else:
            self.model_provider = "ollama"
            self.model_name = model_id if model_id else "qwen2.5-coder:7b"

        self.tool_executor = ToolExecutor()
        
        # Initialize agents
        self.recon_agent = ReconnaissanceAgent(self.model_name, self.tool_executor, self.user_instructions, self.model_provider, self.openrouter_key, log_callback=self.event_callback)
        self.scanner_agent = ScannerAgent(self.model_name, self.tool_executor, self.user_instructions, self.model_provider, self.openrouter_key, log_callback=self.event_callback)
        self.exploit_agent = ExploitationAgent(self.model_name, self.tool_executor, self.user_instructions, self.model_provider, self.openrouter_key, log_callback=self.event_callback)
        
        self.knowledge_base = {'target': target_url, 'mission': user_instructions, 'scan_history': [], 'exploit_attempts': [], 'failures': []}

    def _log(self, message, type="info", data=None):
        console.log(message)
        if self.event_callback:
            try:
                self.event_callback({"type": type, "message": str(message), "data": data})
            except Exception as e:
                console.log(f"Callback Error: {e}")

    def add_extra_info(self, info):
        self._log(f"[bold yellow]EXTRA INFO RECEIVED:[/bold yellow] {info}", type="system")
        self.user_instructions += f"\n[User Update]: {info}"
        # Update agents with new instructions
        self.recon_agent.user_instructions = self.user_instructions
        self.scanner_agent.user_instructions = self.user_instructions
        self.exploit_agent.user_instructions = self.user_instructions
        self.knowledge_base['mission'] = self.user_instructions

    def run_assessment(self):
        provider_display = f"OpenRouter ({self.model_name})" if self.openrouter_key else f"Ollama ({self.model_name})"
        self._log(f"Starting nDrill Professional Security Assessment Suite\nTarget: {self.target_url}\nProvider: {provider_display}", type="phase", data={"phase": "start", "target": self.target_url})
        
        try:
            # 1. Intelligence
            self._log("Phase 1: Information Gathering", type="phase", data={"phase": "recon"})
            recon_results = self.recon_agent.perform_reconnaissance(self.target_url)
            self.knowledge_base['recon'] = recon_results
            self._log(f"Reconnaissance complete: {len(recon_results)} findings.", type="info")

            # 2. Service Discovery
            self._log("Phase 2: Service Enumeration", type="phase", data={"phase": "scan"})
            nmap_output = self.tool_executor.execute_tool("nmap", ["-sV", "--open", "-F", self.target_url], self.target_url)
            self.knowledge_base['nmap'] = nmap_output
            self._log("Service enumeration complete.", type="info", data={"tool": "nmap", "output": nmap_output})

            # 3. Analysis Cycle
            self._log("Phase 3: Automated Vulnerability Analysis", type="phase", data={"phase": "analysis"})
            cycle = 0
            while not self.stop_event.is_set():
                cycle += 1
                self._log(f"Assessment Cycle {cycle}", type="cycle", data={"cycle": cycle})
                
                # Dynamic Scanning
                self._log(f"Cycle {cycle}: Performing specialized scans...", type="info")
                scanner_report = self.scanner_agent.perform_scan(self.target_url, self.knowledge_base['recon'], nmap_output, [])
                if scanner_report:
                    self.knowledge_base['scan_history'].append(scanner_report)
                    self._log(f"Scan report generated.", type="info", data={"report": scanner_report})
                
                # Exploitation development loop
                self._log(f"Cycle {cycle}: Developing assessment scripts...", type="info")
                messages, _ = self.exploit_agent.generate_exploit(self.target_url, scanner_report or {}, self.knowledge_base)
                
                for attempt in range(10): 
                    if self.stop_event.is_set(): break
                    
                    self._log(f"Cycle {cycle}, Analysis Attempt {attempt+1}: Drafting code...", type="info")
                    try:
                        raw_out, ext_json, exploit_data = self.exploit_agent.get_exploit_from_llm(messages)
                    except Exception as e:
                        self._log(f"Agent Error: {e}", type="error")
                        continue
                    
                    if "error" in exploit_data:
                        self._log(f"JSON Error: {exploit_data['error']}", type="error")
                        messages.append({"role": "assistant", "content": raw_out})
                        messages.append({"role": "user", "content": f"SYSTEM: Fix JSON. Error: {exploit_data['error']}. Ensure keys are quoted."})
                        continue

                    if exploit_data.get("exploit_script"):
                        self._log(f"Executing script for attempt {attempt+1}...", type="tool", data={"tool": "python_exploit", "code": exploit_data.get("exploit_script")})
                        res = self._run_exploit(exploit_data)
                        
                        is_success = exploit_data.get("is_goal_achieved", False)
                        success_markers = ["uid=0(root)", "root:x:0:0", "defacement successful", "database_dump_complete", "pwned", "weblogic rce success", "vulnerability confirmed"]
                        if any(k in res.lower() for k in success_markers): 
                            is_success = True
                        
                        if is_success:
                            self._log(f"OBJECTIVE REACHED: {res[:500]}", type="success", data={"output": res})
                            self.generate_final_report()
                            return 
                        else:
                            self._log(f"Attempt {attempt+1} failed. Refining approach...", type="warning")
                            self.knowledge_base['failures'].append({"script": exploit_data.get("exploit_script"), "output": res})
                            messages.append({"role": "assistant", "content": raw_out})
                            truncated_res = (res[:5000] + '... [Output Truncated]') if len(res) > 5000 else res
                            debug_msg = f"EXECUTION OUTPUT:\n{truncated_res}\n\nANALYSIS: The assessment script did not achieve the objective. 1) If 'Connection refused' or 'timed out', the port might be closed or filtered. 2) If 'SyntaxError', fix the Python code. 3) If 404/403, check the URL path. DO NOT USE PLACEHOLDERS. Use the feedback to improve the next version."
                            messages.append({"role": "user", "content": debug_msg})
                    else:
                        self._log("No assessment script in response.", type="warning")
                        messages.append({"role": "assistant", "content": raw_out})
                        messages.append({"role": "user", "content": "You must provide an 'exploit_script' in your JSON."})

                time.sleep(2)

        except KeyboardInterrupt:
            self._log("Assessment terminated by user.", type="system")
        except Exception as e:
            self._log(f"Critical Error: {e}", type="error")
            import traceback
            traceback.print_exc()
        finally:
            self.tool_executor.cleanup()
            self.generate_final_report()

    def _run_exploit(self, data):
        script_content = data["exploit_script"]
        self.knowledge_base['exploit_attempts'].append(data)
        
        try: compile(script_content, "<string>", "exec")
        except SyntaxError as e:
            msg = f"Python SyntaxError: {e.msg} at line {e.lineno}\nCode: {e.text}"
            self._log(msg, type="error")
            return msg

        script_name = f"/tmp/exploit_{uuid.uuid4().hex[:6]}.py"
        if self.tool_executor.write_file_to_container(script_content, script_name):
            self._log(f"Running exploit script {script_name}...", type="info")
            res = self.tool_executor.execute_tool("python3", [script_name], self.target_url)
            self.knowledge_base['last_exploit_result'] = res
            self._log("Exploit Execution Output", type="tool", data={"tool": "python3-exploit-output", "output": res})
            return res
        return "Error: Failed to write script to container."

    def generate_final_report(self):
        import re
        safe_target = re.sub(r'[^a-zA-Z0-9]', '_', self.target_url)
        name = f"ndrill_assessment_report_{safe_target}.md"
        content = f"# nDrill Security Assessment Report: {self.target_url}\n## Mission: {self.user_instructions}\n## Result: {self.knowledge_base.get('last_exploit_result', 'Incomplete')}\n"
        try:
            with open(name, "w") as f: f.write(content)
            self._log(f"Final Report generated: {name}", type="info")
        except Exception as e:
            self._log(f"Error saving report: {e}", type="error")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--comment", default="Perform a security assessment of the target.")
    parser.add_argument("--model", help="Model ID to use (e.g. 'qwen2.5-coder:7b' for Ollama or 'google/gemini-2.0-flash-001' for OpenRouter)")
    parser.add_argument("--openrouter", help="OpenRouter API Key")
    args = parser.parse_args()
    orchestrator = Orchestrator(target_url=args.target, model_id=args.model, user_instructions=args.comment, openrouter_key=args.openrouter)
    orchestrator.run_assessment()