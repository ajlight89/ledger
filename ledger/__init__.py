"""Ledger: an offline desktop personal finance tracker."""

import logging

__version__ = "0.1.0"

# Stay quiet until a front end calls logging.basicConfig(). Without this,
# Python prints every logged warning to the terminal, even during tests.
logging.getLogger(__name__).addHandler(logging.NullHandler())
