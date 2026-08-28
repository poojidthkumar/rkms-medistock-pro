"""
Command-line entry point for RKMS MediStock Pro.
Running `rkms-medistock` in a terminal starts the local server
(database is created in the current folder) and opens the app
in your default browser - same pattern as `jupyter notebook`.
"""
import threading
import time
import webbrowser

import uvicorn

from .app import app

HOST = "127.0.0.1"
PORT = 8000


def _open_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://{HOST}:{PORT}")


def main():
    threading.Thread(target=_open_browser, daemon=True).start()
    print(f"RKMS MediStock Pro running at http://{HOST}:{PORT}")
    print("Press CTRL+C in this window to stop the server.")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
