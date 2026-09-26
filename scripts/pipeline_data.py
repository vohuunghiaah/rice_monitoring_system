"""Convenience entry point; also supports invocation outside the repo root."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.main import main

if __name__ == '__main__':
    raise SystemExit(main())
