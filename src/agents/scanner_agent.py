# src/agents/scanner_agent.py
import json
import re
from rich.console import Console
from rich.panel import Panel
from agents.base_agent import BaseAgent

console = Console()

class ScannerAgent(BaseAgent):
    def __init__(self, model_name, tool_executor, user_instructions, model_provider="ollama", openrouter_key=None):
        super().__init__(model_name, tool_executor, user_instructions, model_provider, openrouter_key)
        self.system_prompt = f"""
        You are the Scanner Agent, an advanced automated security analyst.
        Your goal is to find actionable vulnerabilities using fast, non-interactive tools.
        
        ### CRITICAL JSON RULES:
        1.  **JSON ONLY:** Output PURE JSON. Do not start with "Thought:". Put your reasoning inside the JSON object.
        2.  **NO PLACEHOLDERS:** Never use `...` or `target.com`. Use the ACTUAL TARGET provided in the context.
        3.  **VALID SYNTAX:** Ensure all keys and strings are double-quoted. Escape newlines.

        ### MISSION CONSTRAINTS:
        - **NO DOS:** No `slowhttptest` or `hping3`.
        - **SPEED:** Prioritize `sqlmap --batch`, `ffuf`, `commix --batch`.
        - **NIKTO:** Only use as last resort.

        ### Available Tools:
        - **SQLMap**: `sqlmap -u "<URL>" --batch`
        - **FFUF**: `ffuf -u <URL>/FUZZ -w /usr/share/dirb/wordlists/common.txt`
        - **Commix**: `commix --url="<URL>" --batch`
        - **Wfuzz**: `wfuzz -c -z file,/usr/share/dirb/wordlists/common.txt --hc 404 <URL>/FUZZ`
        - **Nikto**: `nikto -host <URL>` (LAST RESORT)

        ### JSON Structure:
        {{
            "thought": "Reasoning here...",
            "tool_name": "tool",
            "args": ["arg1", "arg2"],
            "is_satisfied": false
        }}
        """

    def _get_llm_response(self, messages, max_attempts=3):
        for attempt in range(max_attempts):
            raw_llm_output = self._chat(messages)
            console.print(Panel(raw_llm_output, title=f"[bold red]Scanner Analysis Reasoning (Attempt {attempt+1})[/bold red]", border_style="red"))
            
            # Helper to sanitize common model mistakes
            if raw_llm_output.strip().startswith("```json"):
                raw_llm_output = raw_llm_output.replace("```json", "").replace("```", "")
            
            extracted_json_str = self.extract_json_from_llm_response(raw_llm_output)
            try:
                # Validate against placeholders
                #if "..." in extracted_json_str or "target.com" in extracted_json_str:
                #    raise ValueError("Output contains placeholders.")
                    
                data = json.loads(extracted_json_str, strict=False)
                return raw_llm_output, extracted_json_str, data
            except (json.JSONDecodeError, ValueError) as e:
                console.log(f"ScannerAgent: JSON Error: {e}")
                if attempt < max_attempts - 1:
                    messages.append({"role": "assistant", "content": raw_llm_output})
                    messages.append({"role": "user", "content": f"SYSTEM: Fix JSON Error: {e}. Return VALID JSON ONLY. Use actual target URL, no placeholders."})
                else: 
                    return raw_llm_output, "", {} # Return empty to avoid crash
        return "", "", {}

    def perform_scan(self, target_url, recon_results, nmap_results, potential_vulnerabilities):
        console.log(f"ScannerAgent: Commencing vulnerability analysis of [bold green]{target_url}[/bold green]")
        agent_history = []
        context = {"target": target_url, "recon": recon_results, "nmap": nmap_results}

        for iteration in range(5):
            console.log(f"ScannerAgent: Analysis cycle iteration {iteration+1}...")
            prompt = f"TARGET: {target_url}\nCONTEXT: {json.dumps(context)}\nHISTORY: {json.dumps(agent_history)}\nMISSION: {self.user_instructions}\n\nOUTPUT NEXT TOOL IN JSON."
            messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": prompt}]
            _, _, suggestion = self._get_llm_response(messages)
            
            if not suggestion: break # Stop if AI fails consistently

            if suggestion.get("is_satisfied") and iteration > 1:
                console.log("[bold green]ScannerAgent is satisfied.[/bold green]")
                break

            tool_name = suggestion.get("tool_name", "").lower()
            tool_args = suggestion.get("args", [])
            if not tool_name: break

            if isinstance(tool_args, str):
                import shlex
                tool_args = shlex.split(tool_args)

            console.log(f"ScannerAgent: Decided to run [bold yellow]{tool_name}[/bold yellow]")
            output = self.tool_executor.execute_tool(tool_name, tool_args, target_url)
            agent_history.append({"tool": tool_name, "args": tool_args, "output": output[:800]})
            
        final_prompt = f"Intel: {json.dumps(agent_history)}. Generate FINAL SCAN REPORT JSON."
        messages.append({"role": "user", "content": final_prompt})
        _, _, final_report = self._get_llm_response(messages)
        return final_report
