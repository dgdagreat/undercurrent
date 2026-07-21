"""Transaction sources — the integration seam.

Every way a ledger can enter the platform (CSV upload today; Plaid, QuickBooks,
or a POS feed tomorrow) is a `TransactionSource`: something that produces
transactions in one normalized schema. Everything downstream — persistence,
scoring, the dashboard — consumes only that schema and never knows where the
rows came from. Adding a connector means adding one small class here, not
touching the scoring engine or the API.
"""

from .base import LEDGER_COLUMNS, SourceError, TransactionSource  # noqa: F401
from .csv_source import CsvSource  # noqa: F401
