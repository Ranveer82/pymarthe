"""
PyMarthe helper subpackage.

Contains higher-level helper functions built on top of the core PyMarthe
classes for model pre-processing, post-processing and declarative input
writing.
"""

# ---- Convenience re-exports (only stdlib is imported at module load time;
#      the MartheModel import stays lazy inside the functions).
from .model_inputs import (
    write_model_inputs,
    apply_model_inputs,
    read_inputs_config,
)
