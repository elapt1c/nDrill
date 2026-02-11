# nDrill: Advanced Security Assessment Suite

nDrill is an autonomous security assessment tool designed for professional security analysts. It leverages advanced language models (via Ollama or OpenRouter) to conduct intelligence gathering, service enumeration, and automated vulnerability analysis.

## Features

- **Autonomous Orchestration**: Managed assessment lifecycle from reconnaissance to final reporting.
- **Intelligence Gathering**: Automated reconnaissance and service discovery.
- **Automated Analysis**: Continuous cycle of vulnerability identification and validation.
- **Professional Reporting**: Generates comprehensive markdown reports of findings and assessment results.
- **Secure Execution**: All assessment scripts are executed within isolated Docker containers.

## Requirements

- Python 3.9+
- Docker (for tool execution)
- Ollama (for local model execution) or an OpenRouter API key

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/ndrill.git
   cd ndrill
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: Ensure requirements.txt exists or install: rich, requests, docker, ollama)*

## Usage

Run a security assessment against a target:

```bash
python ndrill.py --target http://example.com --comment "Identify potential misconfigurations"
```

Using OpenRouter:

```bash
python ndrill.py --target http://example.com --openrouter YOUR_API_KEY --model google/gemini-2.0-flash-001
```

## Disclaimer

This software is intended for **ethical security testing only**. Unauthorized use on systems without explicit permission is illegal. Use responsibly.
