# src/agents/base_agent.py
import json
import ollama
import requests
from rich.console import Console
from rich.panel import Panel

console = Console()

class BaseAgent:
    def __init__(self, model_name, tool_executor, user_instructions, model_provider="ollama", openrouter_key=None):
        self.model_name = model_name
        self.tool_executor = tool_executor
        self.user_instructions = user_instructions
        self.model_provider = model_provider
        self.openrouter_key = openrouter_key

    def _chat(self, messages):
        if self.model_provider == "ollama":
            response = ollama.chat(
                model=self.model_name,
                messages=messages,
                stream=False,
                options={"num_thread": 12}
            )
            return response['message']['content']
        
        elif self.model_provider == "openrouter":
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": self.model_name,
                "messages": messages
            }
            try:
                resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
                resp.raise_for_status()
                return resp.json()['choices'][0]['message']['content']
            except Exception as e:
                console.log(f"[bold red]OpenRouter Error:[/bold red] {e}")
                if hasattr(e, 'response') and e.response:
                    console.log(f"Response: {e.response.text}")
                return "{}" # Return empty string to trigger retry or fail gracefully

    @staticmethod
    def extract_json_from_llm_response(response_text):
        import re
        cleaned_text = re.sub(r'```json\s*', '', response_text)
        cleaned_text = re.sub(r'```\s*', '', cleaned_text)
        start = cleaned_text.find('{')
        end = cleaned_text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return cleaned_text[start:end+1]
        return response_text
