from flask import Flask, request, render_template, jsonify, stream_with_context
import subprocess
import sys
import os
import time
import threading
from werkzeug.utils import secure_filename

# OpenRouter API integration
OPENROUTER_API_KEY = "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"
OPENROUTER_MODEL = "arcee-ai/trinity-large-preview:free"
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

app = Flask(__name__)

def generate_openrouter_response(prompt, context=None):
    """Generate a response using OpenRouter API"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "nDrill Web UI"
    }
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are a security assessment assistant."},
        ]
    }
    
    # Add user instructions as context if provided
    if context:
        payload["messages"].append({
            "role": "user", 
            "content": f"Context: {context}\n\nUser request: {prompt}"
        })
    else:
        payload["messages"].append({
            "role": "user", 
            "content": prompt
        })
    
    def generate():
        with subprocess.Popen(
            [sys.executable, "-m", "requests", "post", OPENROUTER_ENDPOINT,
             "-H", "Authorization: Bearer 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",
             "-H", "Content-Type: application/json",
             "-d", '{"model":"arcee-ai/trinity-large-preview:free", "messages":[{"role":"system","content":"You are a security assessment assistant."},{"role":"user","content":"' + prompt + '"}]}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc:
            while True:
                line = proc.stdout.readline()
                if line:
                    yield line.decode('utf-8')
                elif proc.poll() is not None:
                    break
    
    return generate()

@app.route('/')
def index():
    return '''
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>nDrill Web UI</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/abide.min.js" defer></script>
    </head>
    <body class="bg-gray-100">
        <div class="max-w-2xl mx-auto p-6">
            <h1 class="text-2xl font-bold text-blue-600 mb-4">nDrill Web Assessment</h1>
            <div class="bg-white rounded-lg shadow p-6 mb-6">
                <form wire:submit.prevent class="space-y-4" x-data x-guide>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Target URL</label>
                            <input type="url" name="target" class="input input-primary w-full" required>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Assessment Context</label>
                            <textarea name="context" rows="4" class="input input-primary w-full"></textarea>
                        </div>
                    </div>
                    <div class="text-right">
                        <button type="submit" class="btn btn-primary" x-on:click.out="reset()">Run Assessment</button>
                    </div>
                </form>
            </div>
            <div id="results" class="mt-6"></div>
        </div>
        <script>
            document.addEventListener('alpine:init', () => {
                // Alpine.js initialization
            });
        </script>
    </body>
    </html>
    '''

@app.route('/run', methods=['POST'])
def run_assessment():
    target = request.form['target']
    context = request.form.get('context', '')
    
    # Start the assessment in a background thread to keep the server responsive
    def run_assessment():
        # Simulate the assessment process with progress updates
        yield f"data: {{\"status\":\"progress\", \"message\":\"Starting assessment against {target}\"}}\n\n"
        time.sleep(1)
        yield f"data: {{\"status\":\"progress\", \"message\":\"Running reconnaissance...\"}}\n\n"
        time.sleep(1)
        yield f"data: {{\"status\":\"progress\", \"message\":\"Analyzing services...\"}}\n\n"
        time.sleep(1)
        yield f"data: {{\"status\":\"results\", \"message\":\"Assessment complete! Results will be saved.\"}}\n\n"
        # In a real implementation, you'd save results to a file
        yield f"data: {{\"status\":\"complete\", \"output\":\"assessment_report_{int(time.time())}.md\"}}\n\n"
    
    return jsonify(status='running'), 200, {
        'X-Accel-Buffering': 'no',
        'Content-Type': 'text/event-stream'
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)