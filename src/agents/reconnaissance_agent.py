# src/agents/reconnaissance_agent.py
import json
import re
from rich.console import Console
from rich.panel import Panel
from agents.base_agent import BaseAgent

console = Console()

class ReconnaissanceAgent(BaseAgent):
    def __init__(self, model_name, tool_executor, user_instructions, model_provider="ollama", openrouter_key=None):
        super().__init__(model_name, tool_executor, user_instructions, model_provider, openrouter_key)
        self.system_prompt = f"""
        You are the Reconnaissance Agent.
        
        ### CRITICAL JSON RULES:
        1.  **JSON ONLY:** Output PURE JSON. Put reasoning in "thought".
        2.  **NO PLACEHOLDERS:** Use ACTUAL target.
        3.  **VALID SYNTAX:** Escape newlines.

        ### MISSION: {self.user_instructions}
        
        ### Tools: curl, nmap
        
        ### JSON Structure:
        {{
            "thought": "Reasoning...",
            "tool_name": "nmap",
            "args": ["-sV", "TARGET"]
        }}
        """

    def _get_llm_response(self, messages, max_attempts=3):
        for attempt in range(max_attempts):
            raw_llm_output = self._chat(messages)
            console.print(Panel(raw_llm_output, title=f"[bold blue]Intelligence Analysis Reasoning (Attempt {attempt+1})[/bold blue]", border_style="blue"))
            
            if raw_llm_output.strip().startswith("```json"):
                raw_llm_output = raw_llm_output.replace("```json", "").replace("```", "")
                
            extracted = self.extract_json_from_llm_response(raw_llm_output)
            try:
                #if "..." in extracted: raise ValueError("Placeholders detected.")
                return raw_llm_output, extracted, json.loads(extracted, strict=False)
            except Exception as e:
                if attempt < max_attempts - 1:
                    messages.append({"role": "assistant", "content": raw_llm_output})
                    messages.append({"role": "user", "content": f"SYSTEM: Fix JSON Error: {e}. Valid JSON Only. No placeholders."})
                else: raise
        return "", "", {}

    def perform_reconnaissance(self, target_url):
        console.log(f"ReconnaissanceAgent: Initiating information gathering for [bold green]{target_url}[/bold green]")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"TARGET: {target_url}\nMISSION: {self.user_instructions}"}
        ]
        try:
            _, _, cmd_json = self._get_llm_response(messages)
            tool_name = cmd_json.get("tool_name", "curl")
            tool_args = cmd_json.get("args", ["-s", "-I", target_url])
            
            if isinstance(tool_args, str):
                import shlex
                tool_args = shlex.split(tool_args)

            output = self.tool_executor.execute_tool(tool_name, tool_args, target_url)
            
            messages.append({"role": "assistant", "content": json.dumps(cmd_json)})
            messages.append({"role": "user", "content": f"DATA: {output}. Synthesize report."})
            _, _, report = self._get_llm_response(messages)
            return report
        except Exception as e:
            return {"error": str(e)}
