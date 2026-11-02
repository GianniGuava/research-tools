"""Shared helpers for the automated tests (standard library only)."""
import importlib.machinery
import importlib.util
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WEBSEARCH = REPO / "bin" / "websearch"
FAKE = REPO / "tests" / "fake_searxng.py"


def load_websearch():
    """Import bin/websearch (no .py suffix) as a module."""
    loader = importlib.machinery.SourceFileLoader("websearch", str(WEBSEARCH))
    spec = importlib.util.spec_from_loader("websearch", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_file(path, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if Path(path).exists() and Path(path).read_text().strip():
            return Path(path).read_text().strip()
        time.sleep(0.05)
    raise AssertionError(f"{path} never appeared")


def kill_pidfile(path):
    try:
        os.kill(int(Path(path).read_text().strip()), signal.SIGTERM)
    except (FileNotFoundError, ValueError, ProcessLookupError):
        pass


class TempState:
    """A private state folder and environment for one test, so tests never touch the real ones."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="rt-test-"))
        self.env = dict(os.environ, XDG_STATE_HOME=str(self.dir / "state"), XDG_CONFIG_HOME=str(self.dir / "config"))
        self.env.pop("SEARXNG_URL", None)
        self.env.pop("S2_API_KEY", None)

    def path(self, name):
        return self.dir / name

    def run(self, *args, timeout=30, **extra_env):
        env = dict(self.env, **extra_env)
        start = time.monotonic()
        p = subprocess.run([sys.executable, str(WEBSEARCH), *args], capture_output=True, text=True,
                           timeout=timeout, env=env)
        p.elapsed = time.monotonic() - start
        return p
