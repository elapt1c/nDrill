# src/agents/reconnaissance_agent.py
import json
import re
import shlex
from rich.console import Console
from rich.panel import Panel
from agents.base_agent import BaseAgent

console = Console()

class ReconnaissanceAgent(BaseAgent):
    def __init__(self, model_name, tool_executor, user_instructions, model_provider="ollama", openrouter_key=None, log_callback=None):
        super().__init__(model_name, tool_executor, user_instructions, model_provider, openrouter_key, log_callback)
        self.system_prompt = f"""
        You are the nDrill Reconnaissance Agent.
        Your goal is to gather initial intelligence about the target to identify attack surfaces.
        
        ### OPERATIONAL GUIDELINES:
        1.  **JSON ONLY:** Output a single JSON object.
        2.  **TOOLS AVAILABLE:** curl, nmap, whois, dnsutils (dig/nslookup), ping.
        3.  **PRECISION:** Focus on the target provided.
        4.  **PHASED APPROACH:** 
            - Phase 1: Identify technology stack, headers, and basic structure.
            - Phase 2: Identify open ports and services (if not already provided).

        ### MISSION: {self.user_instructions}
        
        ### JSON RESPONSE FORMAT (STRICT):
        {{
            "thought": "Reasoning about why this tool/command is necessary.",
            "tool_name": "curl",
            "args": ["-I", "-L", "TARGET_URL"],
            "explanation": "What we hope to find."
        }}
        """

    def _get_llm_response(self, messages, max_attempts=3):
        for attempt in range(max_attempts):
            raw_llm_output = self._chat(messages)
            extracted = self.extract_json_from_llm_response(raw_llm_output)
            try:
                return raw_llm_output, extracted, json.loads(extracted, strict=False)
            except Exception as e:
                if attempt < max_attempts - 1:
                    messages.append({"role": "assistant", "content": raw_llm_output})
                    messages.append({"role": "user", "content": f"SYSTEM: Fix JSON Error: {e}. Valid JSON Only. No markdown blocks."})
                else: raise
        return "", "", {}

    def perform_reconnaissance(self, target_url):
        console.log(f"ReconnaissanceAgent: Initiating information gathering for [bold green]{target_url}[/bold green]")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"TARGET: {target_url}\nMISSION: {self.user_instructions}. Start with an initial probe."}
        ]
        try:
            _, _, cmd_json = self._get_llm_response(messages)
            if cmd_json.get("thought"):
                self._log(f"Recon Thought: {cmd_json['thought']}", type="thought")

            tool_name = cmd_json.get("tool_name", "curl")
            tool_args = cmd_json.get("args", ["-s", "-I", target_url])
            
            # Replace placeholder TARGET_URL with actual target
            tool_args = [a.replace("TARGET_URL", target_url).replace("TARGET", target_url) for a in tool_args]

            self._log(f"Running Recon Tool: {tool_name} {' '.join(tool_args)}", type="tool", data={"tool": tool_name, "args": tool_args})
            output = self.tool_executor.execute_tool(tool_name, tool_args, target_url)
            self._log(f"Recon Tool Output", type="tool", data={"tool": tool_name, "output": output})
            
            # Final synthesis
            messages.append({"role": "assistant", "content": json.dumps(cmd_json)})
            messages.append({"role": "user", "content": f"TOOL OUTPUT:\n{output}\n\nSynthesize a structured report of the technology stack and potential attack vectors. Return as JSON."})
            
            _, _, report = self._get_llm_response(messages)
            if report.get("thought"):
                self._log(f"Recon Analysis: {report['thought']}", type="thought")
            return report
        except Exception as e:
            self._log(f"Recon Error: {e}", type="error")
            return {"error": str(e)}
