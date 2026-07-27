#!/usr/bin/env python3
"""
Write MARTHE model inputs (grids and lists) from a configuration file.

This is a thin command-line wrapper around
``pymarthe.helpers.model_inputs.write_model_inputs``. It reads a YAML (or JSON)
configuration file describing the values to set on the model grid-like
properties (MartheField : permh, emmca, emmli, kepon, ...) and list-like
properties (MarthePump : aqpump, rivpump ; MartheSoil : soil), applies them
with PyMarthe and writes the updated properties back into the MARTHE input
files.

Usage
-----
    python scripts/write_model_inputs.py path/to/model_inputs.yaml
    python scripts/write_model_inputs.py path/to/model_inputs.yaml --no-write
    python scripts/write_model_inputs.py path/to/model_inputs.yaml --quiet

See ``examples/model_inputs.yaml`` for a documented configuration example.
"""

import os
import sys

# ---- Make PyMarthe importable when running the script from a source checkout
#      (i.e. without having pip-installed the package).
try:
    import pymarthe  # noqa: F401
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymarthe.helpers.model_inputs import main


if __name__ == '__main__':
    main()
