"""Make the package importable when running tests from the repo without install."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
