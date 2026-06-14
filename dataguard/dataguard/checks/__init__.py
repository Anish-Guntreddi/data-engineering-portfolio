"""Pure data-quality checks.

Every check in this package is a pure callable ``(data, config) -> CheckResult``.
None of these modules import any infrastructure libraries (no psycopg2, no
sqlalchemy, no kafka). They depend only on numpy and pandas, which means the
whole package unit-tests on the host without Docker.
"""

from dataguard.checks.base import CheckResult, Severity
from dataguard.checks.schema_check import schema_check
from dataguard.checks.null_check import null_check
from dataguard.checks.range_check import range_check
from dataguard.checks.freshness_check import freshness_check
from dataguard.checks.drift import psi, ks_statistic, drift_check

__all__ = [
    "CheckResult",
    "Severity",
    "schema_check",
    "null_check",
    "range_check",
    "freshness_check",
    "psi",
    "ks_statistic",
    "drift_check",
]
