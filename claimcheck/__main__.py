"""Allow `python -m claimcheck`."""

import sys

from claimcheck.cli import main

if __name__ == "__main__":
    sys.exit(main())
