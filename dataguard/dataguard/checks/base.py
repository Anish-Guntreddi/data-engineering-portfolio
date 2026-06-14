"""Core data types shared by every check.

A ``Check`` is a pure callable with the signature ``(data, config) -> CheckResult``
where ``data`` is a pandas ``DataFrame`` and ``config`` is a plain ``dict``. No
infrastructure imports are allowed here so the checks unit-test on the host.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict


# Severity is intentionally a small set of strings rather than an Enum so it
# serialises trivially to JSON / SQL without any custom encoders.
class Severity:
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    ALL = ("info", "warning", "critical")

    # Weight used by the scoring aggregator. Higher = matters more.
    WEIGHTS: Dict[str, float] = {
        "info": 1.0,
        "warning": 2.0,
        "critical": 3.0,
    }


@dataclass
class CheckResult:
    """The outcome of running a single check against a single table/column.

    Attributes
    ----------
    check:    name of the check that produced this result (e.g. ``"null_check"``).
    table:    table the check ran against.
    column:   column the check ran against (``""`` for table-level checks).
    passed:   whether the check passed.
    score:    a continuous quality signal in ``[0.0, 1.0]`` (1.0 == perfect).
    detail:   human-readable explanation, always populated.
    severity: one of ``Severity.ALL``; drives scoring weight.
    """

    check: str
    table: str
    column: str
    passed: bool
    score: float
    detail: str
    severity: str = Severity.WARNING

    def __post_init__(self) -> None:
        # Defensive: clamp the score so a buggy check can never push the
        # aggregate quality score outside [0, 100].
        if self.score < 0.0:
            self.score = 0.0
        elif self.score > 1.0:
            self.score = 1.0
        if self.severity not in Severity.ALL:
            self.severity = Severity.WARNING

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (used by the runner when persisting)."""
        return asdict(self)
