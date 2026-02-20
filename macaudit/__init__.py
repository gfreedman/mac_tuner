"""Mac Audit — Mac System Health Inspector & Auditor"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("macaudit")
except PackageNotFoundError:
    __version__ = "dev"

__author__ = "Mac Audit"
