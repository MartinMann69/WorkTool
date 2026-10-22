"""Start TSLibrary; --admin or --library opens the chosen workspace directly."""

import sys

from tslibrary_ui.app import main


if __name__ == "__main__":
    sys.exit(main())
