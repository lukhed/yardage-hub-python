"""Python client for the yardage-hub golf course API."""

__version__ = "0.1.1"

from .client import BASE_URL, DOCS_URL, YardageHub, YardageHubError

__all__ = ["YardageHub", "YardageHubError", "BASE_URL", "DOCS_URL"]
