# src/agents/scanner_agent.py
import json
import re
from rich.console import Console
from rich.panel import Panel
from agents.base_agent import BaseAgent

console = Console()

class ScannerAgent(BaseAgent):
    def __init__(self, model_name, tool_executor, user_instructions, model_provider="ollama", openrouter_key=None, log_callback=None):
        super().__init__(model_name, tool_executor, user_instructions, model_provider, openrouter_key, log_callback)
        self.system_prompt = f"""
        You are the nDrill Scanner Agent.
        Your goal is to identify specific vulnerabilities using specialized security tools.
        
        ### OPERATIONAL GUIDELINES:
        1.  **JSON ONLY:** Output a single JSON object.
        2.  **TOOLS AVAILABLE:** nmap, nikto, sqlmap, gobuster, ffuf, dirb, hydra, wfuzz, commix.
        3.  **PRECISION:** Focus on the target provided.
        4.  **ITERATIVE:** Run tools, analyze output, and decide if more scanning is needed.

        ### MISSION: {self.user_instructions}
        
        ### JSON RESPONSE FORMAT (STRICT):
        {{
            "thought": "Reasoning about why this tool/command is necessary.",
            "tool_name": "nmap",
            "args": ["-sV", "--script=http-enum", "TARGET_URL"],
            "is_satisfied": false,
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
                    messages.append({"role": "user", "content": f"SYSTEM: Fix JSON Error: {e}. Valid JSON Only."})
                else: raise
        return "", "", {}

    def perform_scan(self, target_url, recon_results, nmap_results, potential_vulnerabilities):
        console.log(f"ScannerAgent: Commencing vulnerability analysis of [bold green]{target_url}[/bold green]")
        agent_history = []
        context = {"target": target_url, "recon": recon_results, "nmap": nmap_results}

        for iteration in range(3): # Limit iterations for speed
            console.log(f"ScannerAgent: Analysis cycle iteration {iteration+1}...")
            prompt = f"TARGET: {target_url}\nCONTEXT: {json.dumps(context)}\nHISTORY: {json.dumps(agent_history)}\nMISSION: {self.user_instructions}\n\nOUTPUT NEXT TOOL IN JSON."
            messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}]
            _, _, suggestion = self._get_llm_response(messages)
            
            if not suggestion: break

            if suggestion.get("thought"):
                self._log(f"Scanner Thought (Iter {iteration+1}): {suggestion['thought']}", type="thought")

            if suggestion.get("is_satisfied"):
                self._log("ScannerAgent is satisfied with current results.", type="info")
                break

            tool_name = suggestion.get("tool_name", "").lower()
            tool_args = suggestion.get("args", [])
            if not tool_name: break

            # Replace placeholders
            tool_args = [a.replace("TARGET_URL", target_url).replace("TARGET", target_url) for a in tool_args]

            self._log(f"Running Scanner Tool: {tool_name} {' '.join(tool_args)}", type="tool", data={"tool": tool_name, "args": tool_args})
            output = self.tool_executor.execute_tool(tool_name, tool_args, target_url)
            self._log(f"Scanner Tool Output", type="tool", data={"tool": tool_name, "output": output})
            agent_history.append({"tool": tool_name, "args": tool_args, "output": output[:1000]})
            
        final_prompt = f"History: {json.dumps(agent_history)}. Generate a summary of identified vulnerabilities and attack vectors in JSON."
        messages.append({"role": "user", "content": final_prompt})
        _, _, final_report = self._get_llm_response(messages)
        if final_report.get("thought"):
            self._log(f"Scan Final Analysis: {final_report['thought']}", type="thought")
        return final_report
