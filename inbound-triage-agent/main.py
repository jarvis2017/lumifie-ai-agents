#!/usr/bin/env python3
"""Entry point so you can run the demo with zero install:

    python main.py --mock-email      # triage the bundled mock payload (offline OK)
    python main.py --serve           # run the FastAPI webhook

If the package isn't installed, we add ./src to the path so it still runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from inbound_triage.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
