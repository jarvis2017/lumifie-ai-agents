#!/usr/bin/env python3
"""Entry point so you can run the demo with zero install:

    python main.py demo              # ingest the demo docs and answer (offline OK)
    python main.py ask "..."         # answer a question over the store
    python main.py serve             # run the FastAPI server

If the package isn't installed, we add ./src to the path so it still runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from rag_chatbot.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
