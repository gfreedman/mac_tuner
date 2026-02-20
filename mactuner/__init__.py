"""MacTuner — Mac System Health Inspector & Tuner"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("mactuner")
except PackageNotFoundError:
    __version__ = "dev"

__author__ = "MacTuner"
