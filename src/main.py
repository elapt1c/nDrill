# src/main.py
import os
import json
import argparse
import ollama
import subprocess
import uuid
import time
import sys

from rich.console import Console
from rich.text import Text
from rich.panel import Panel

from agents.reconnaissance_agent import ReconnaissanceAgent
from agents.scanner_agent import ScannerAgent
from agents.exploitation_agent import ExploitationAgent
from utils.tool_executor import ToolExecutor

console = Console()

class Orchestrator:
    def __init__(self, target_url, model_id=None, user_instructions="", openrouter_key=None):
        self.target_url = target_url
        self.user_instructions = user_instructions
        self.openrouter_key = openrouter_key
        
        if self.openrouter_key:
            self.model_provider = "openrouter"
            # Use provided model_id or default to gemini-2.0-flash
            self.model_name = model_id if model_id else "google/gemini-2.0-flash-001" 
        else:
            self.model_provider = "ollama"
            # Use provided model_id or default to qwen2.5-coder:7b
            self.model_name = model_id if model_id else "qwen2.5-coder:7b"

        self.tool_executor = ToolExecutor()
        
        # Initialize agents
        self.recon_agent = ReconnaissanceAgent(self.model_name, self.tool_executor, self.user_instructions, self.model_provider, self.openrouter_key)
        self.scanner_agent = ScannerAgent(self.model_name, self.tool_executor, self.user_instructions, self.model_provider, self.openrouter_key)
        self.exploit_agent = ExploitationAgent(self.model_name, self.tool_executor, self.user_instructions, self.model_provider, self.openrouter_key)
        
        self.knowledge_base = {'target': target_url, 'mission': user_instructions, 'scan_history': [], 'exploit_attempts': [], 'failures': []}

    def run_assessment(self):
        provider_display = f"OpenRouter ({self.model_name})" if self.openrouter_key else f"Ollama ({self.model_name})"
        console.print(Panel(f"Starting nDrill Professional Security Assessment Suite\nTarget: [bold green]{self.target_url}[/bold green]\nProvider: [bold blue]{provider_display}[/bold blue]", title="nDrill Orchestrator"))
        
        try:
            # 1. Intelligence
            console.log("[bold cyan]Phase 1: Information Gathering[/bold cyan]")
            recon_results = self.recon_agent.perform_reconnaissance(self.target_url)
            self.knowledge_base['recon'] = recon_results

            # 2. Service Discovery
            console.log("[bold cyan]Phase 2: Service Enumeration[/bold cyan]")
            nmap_output = self.tool_executor.execute_tool("nmap", ["-sV", "--open", "-F", self.target_url], self.target_url)
            self.knowledge_base['nmap'] = nmap_output

            # 3. Analysis Cycle
            console.log("[bold red]Phase 3: Automated Vulnerability Analysis[/bold red]")
            cycle = 0
            while True:
                cycle += 1
                console.print(Panel(f"Assessment Cycle {cycle}", border_style="yellow"))
                
                # Dynamic Scanning
                scanner_report = self.scanner_agent.perform_scan(self.target_url, self.knowledge_base['recon'], nmap_output, [])
                if scanner_report:
                    self.knowledge_base['scan_history'].append(scanner_report)
                
                # Exploitation development loop
                messages, _ = self.exploit_agent.generate_exploit(self.target_url, scanner_report or {}, self.knowledge_base)
                
                for attempt in range(10): 
                    console.log(f"Cycle {cycle}, Analysis Attempt {attempt+1}: Developing Assessment Script...")
                    try:
                        raw_out, ext_json, exploit_data = self.exploit_agent.get_exploit_from_llm(messages)
                    except Exception as e:
                        console.log(f"[red]Agent Error:[/red] {e}")
                        continue
                    
                    if "error" in exploit_data:
                        console.log(f"[red]JSON Error:[/red] {exploit_data['error']}")
                        messages.append({"role": "assistant", "content": raw_out})
                        messages.append({"role": "user", "content": f"SYSTEM: Fix JSON. Error: {exploit_data['error']}. Ensure keys are quoted."})
                        continue

                    if exploit_data.get("exploit_script"):
                        res = self._run_exploit(exploit_data)
                        
                        is_success = exploit_data.get("is_goal_achieved", False)
                        # Check for more definitive success markers in the output
                        success_markers = ["uid=0(root)", "root:x:0:0", "defacement successful", "database_dump_complete", "pwned"]
                        if any(k in res.lower() for k in success_markers): 
                            is_success = True
                        
                        if is_success:
                            console.print(Panel(f"[bold green]OBJECTIVE REACHED[/bold green]\n\n{res}", title="Assessment Objective Achieved"))
                            self.generate_final_report()
                            return 
                        else:
                            console.log(f"[yellow]Attempt failed. Refining...[/yellow]")
                            self.knowledge_base['failures'].append({"script": exploit_data.get("exploit_script"), "output": res})
                            messages.append({"role": "assistant", "content": raw_out})
                            truncated_res = (res[:5000] + '... [Output Truncated]') if len(res) > 5000 else res
                            debug_msg = f"EXECUTION OUTPUT:\n{truncated_res}\n\nANALYSIS: The assessment script did not achieve the objective. 1) If 'Connection refused' or 'timed out', the port might be closed or filtered. 2) If 'SyntaxError', fix the Python code. 3) If 404/403, check the URL path. DO NOT USE PLACEHOLDERS."
                            messages.append({"role": "user", "content": debug_msg})
                    else:
                        console.log("[yellow]No assessment script in response.[/yellow]")
                        messages.append({"role": "assistant", "content": raw_out})
                        messages.append({"role": "user", "content": "You must provide an 'exploit_script' in your JSON."})

                time.sleep(2)

        except KeyboardInterrupt:
            console.log("[bold red]Assessment terminated by user.[/bold red]")
        except Exception as e:
            console.log(f"[bold red]Critical Error:[/bold red] {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.tool_executor.cleanup()
            self.generate_final_report()

    def _run_exploit(self, data):
        console.log("[bold red]EXECUTING ASSESSMENT SCRIPT[/bold red]")
        script_content = data["exploit_script"]
        self.knowledge_base['exploit_attempts'].append(data)
        
        try: compile(script_content, "<string>", "exec")
        except SyntaxError as e:
            return f"Python SyntaxError: {e.msg} at line {e.lineno}\nCode: {e.text}"

        script_name = f"/tmp/exploit_{uuid.uuid4().hex[:6]}.py"
        if self.tool_executor.write_file_to_container(script_content, script_name):
            res = self.tool_executor.execute_tool("python3", [script_name], self.target_url)
            self.knowledge_base['last_exploit_result'] = res
            console.log(f"Exploit Result:\n[dim]{res[:2000]}...[/dim]")
            return res
        return "Error: Failed to write script to container."

    def generate_final_report(self):
        import re
        safe_target = re.sub(r'[^a-zA-Z0-9]', '_', self.target_url)
        name = f"ndrill_assessment_report_{safe_target}.md"
        content = f"# nDrill Security Assessment Report: {self.target_url}\n## Mission: {self.user_instructions}\n## Result: {self.knowledge_base.get('last_exploit_result', 'Incomplete')}\n"
        try:
            with open(name, "w") as f: f.write(content)
            console.print(Panel(f"Final Report: {name}", title="Done"))
        except Exception as e:
            console.print(f"[red]Error saving report:[/red] {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--comment", default="Perform a security assessment of the target.")
    parser.add_argument("--model", help="Model ID to use (e.g. 'qwen2.5-coder:7b' for Ollama or 'google/gemini-2.0-flash-001' for OpenRouter)")
    parser.add_argument("--openrouter", help="OpenRouter API Key")
    args = parser.parse_args()
    orchestrator = Orchestrator(target_url=args.target, model_id=args.model, user_instructions=args.comment, openrouter_key=args.openrouter)
    orchestrator.run_assessment()