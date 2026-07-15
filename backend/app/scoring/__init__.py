"""Pure, framework-free scoring package.

Nothing in here imports FastAPI or SQLAlchemy models — the engine takes plain
DataFrames in and returns a plain result object. That keeps the interesting
logic unit-testable and easy to walk through in an interview.
"""

from .engine import score_business  # noqa: F401
