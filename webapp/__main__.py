"""Launch the SignalGuard local web app:  python -m webapp  [--port 8765] [--no-browser]"""

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="SignalGuard local web app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    url = f"http://{args.host}:{args.port}"
    print(f"SignalGuard web app -> {url}")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run("webapp.server:app", host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
