#!/usr/bin/env python3
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="nDrill: Advanced Automated Security Assessment Suite")
    parser.add_argument("--target", required=True, help="Target URL for assessment")
    parser.add_argument("--comment", default="Perform a security assessment of the target.", help="Assessment objectives or constraints")
    parser.add_argument("--model", help="Model ID to use (Ollama or OpenRouter)")
    parser.add_argument("--openrouter", help="OpenRouter API Key")
    
    args = parser.parse_args()
    
    # We need to import Orchestrator here to avoid path issues
    from main import Orchestrator
    
    orchestrator = Orchestrator(
        target_url=args.target, 
        model_id=args.model, 
        user_instructions=args.comment, 
        openrouter_key=args.openrouter
    )
    orchestrator.run_assessment()
