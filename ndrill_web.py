#!/usr/bin/env python3
import sys
import os
import uvicorn

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

if __name__ == "__main__":
    from web.server import socket_app
    print("Starting nDrill Web UI on http://localhost:8000")
    # Run the socket_app (ASGIApp) which contains BOTH FastAPI and Socket.IO
    uvicorn.run(socket_app, host="0.0.0.0", port=8000, log_level="info")
