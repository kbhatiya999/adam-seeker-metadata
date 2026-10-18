"""`seeker-chat`: start the Chainlit app from the repository root (it reads data/ and eval/ there)."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="seeker-chat", description="Start the chat app (Chainlit).")
    parser.add_argument("--port", default=os.environ.get("SEEKER_CHAT_PORT", "8000"))
    parser.add_argument("--headless", action="store_true", help="do not open a browser")
    args = parser.parse_args(argv)
    here = Path(__file__).resolve().parent
    app_dir = here.parent.parent   # apps/chat: holds .chainlit/config.toml and chainlit.md
    env = {**os.environ, "SEEKER_ROOT": os.environ.get("SEEKER_ROOT") or os.getcwd()}
    command = [sys.executable, "-m", "chainlit", "run", str(here / "app.py"), "--port", str(args.port)]
    return subprocess.call(command + (["--headless"] if args.headless else []), cwd=app_dir, env=env)


if __name__ == "__main__":
    sys.exit(main())
