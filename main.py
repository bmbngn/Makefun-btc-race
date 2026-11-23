"""Entry point for the btcbot (agent-fun/bars-replay/v1, Python 3.13 stdlib).

The grader runs `python3 -P -s /bot/main.py` with PYTHONHASHSEED=0; -P
leaves this directory off sys.path, so it is added back explicitly (and
vendor/ for the kit SDK shim) before importing the framework.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_VENDOR = os.path.join(_HERE, "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from btcbot.bot import main  # noqa: E402

if __name__ == "__main__":
    main()
