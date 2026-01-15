#!/usr/bin/env python3
"""
Simple HTTP server to view the generated events page locally.
Serves the output directory on http://localhost:8000
"""

import http.server
import socketserver
import os
from pathlib import Path

PORT = 8000
DIRECTORY = "output"


def main():
    # Get project root (parent of scripts directory)
    project_root = Path(__file__).parent.parent
    output_dir = project_root / DIRECTORY

    # Check if output directory exists
    if not output_dir.exists():
        print(f"Output directory '{output_dir}' does not exist.")
        print("Run the scraper first: python -m src.main")
        return

    os.chdir(output_dir)

    handler = http.server.SimpleHTTPRequestHandler

    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"Serving events page at http://localhost:{PORT}")
        print(f"Open http://localhost:{PORT}/events.html in your browser")
        print("Press Ctrl+C to stop the server")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
