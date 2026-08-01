from __future__ import annotations
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app


def find_available_port(start_port: int = 7861, max_attempts: int = 10) -> int:
    """Finds an available TCP port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def main():
    port = find_available_port(7861)
    server_url = f"http://127.0.0.1:{port}"

    print("==================================================")
    print("      LAUNCHING RICK SOFTWARE ASSISTANT UI        ")
    print(f"      Server URL: {server_url}                   ")
    print("==================================================\n")

    # Start Gradio background server
    def start_gradio_server():
        app.demo.launch(
            server_name="127.0.0.1",
            server_port=port,
            show_api=False,
            quiet=True,
            css=app.CUSTOM_CSS,
            prevent_thread_lock=True,
        )

    start_gradio_server()

    # Try launching in native desktop window via pywebview
    use_native_window = False
    try:
        import webview
        use_native_window = True
        print("[OK] PyWebView detected. Launching native desktop window...")
        webview.create_window(
            title="Rick Software Assistant",
            url=server_url,
            width=1340,
            height=880,
            resizable=True,
            min_size=(1000, 700),
        )
        webview.start()
    except Exception as e:
        print(f"[!] Native PyWebView launch skipped ({e}). Falling back to browser view.")
        use_native_window = False

    if not use_native_window:
        print(f"[OK] Opening {server_url} in default web browser...")
        webbrowser.open(server_url)
        print("Press Ctrl+C in terminal to stop server.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down server.")


if __name__ == "__main__":
    main()
