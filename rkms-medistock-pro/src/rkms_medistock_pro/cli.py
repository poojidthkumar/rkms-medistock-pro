"""
Command-line entry point for RKMS MediStock Pro.
Running `rkms-medistock` in a terminal starts the local server
(database is created next to the installed package) and opens the
app in your default browser - same pattern as `jupyter notebook`.

For multi-laptop / network setups: set RKMS_HOST=0.0.0.0 on the
central computer so other laptops on the same network can reach it
at http://<this-computer's-LAN-IP>:8000, and set RKMS_DATABASE_URL
to a shared PostgreSQL connection string (see README).
"""
import os
import threading
import time
import webbrowser

import uvicorn

from .app import app

HOST = os.environ.get("RKMS_HOST", "127.0.0.1")
PORT = int(os.environ.get("RKMS_PORT", "8000"))


def _open_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{PORT}")


def main():
    threading.Thread(target=_open_browser, daemon=True).start()
    print(f"RKMS MediStock Pro running at http://{HOST}:{PORT}")
    if HOST == "0.0.0.0":
        print("Network mode: other laptops on this network can connect using this computer's LAN IP.")
    print("Press CTRL+C in this window to stop the server.")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
