"""Event schema and deterministic generators.

PURE module: imports only the Python standard library (random, time). No
kafka / postgres imports here so it can be unit-tested on the host.

Event schema (a plain dict, JSON-serializable):
    {
        "event_id":   str,   # unique id within a batch/stream
        "user_id":    str,   # "user-<n>"
        "session_id": str,   # "sess-<n>"
        "event_type": str,   # one of EVENT_TYPES
        "event_ts":   float, # epoch seconds (UTC)
    }

There are two generators:

* ``generate_batch(seed, n, start_ts, step_seconds)`` — fully deterministic.
  Given the same arguments it always yields the exact same list of events, so
  golden values can be baked into unit tests.

* ``stream_events(seed, rate_per_sec, ...)`` — an infinite generator used by the
  containerized producer. It is seeded too (so a run is reproducible) but is
  meant to be consumed live, stamping each event with the current wall clock.
"""

from __future__ import annotations

import random
import time
from typing import Dict, Iterator, List

# Ordered so a seeded RNG produces stable choices.
EVENT_TYPES: List[str] = [
    "page_view",
    "session_start",
    "add_to_cart",
    "purchase",
]

# Relative weights used by the deterministic generator. page_view dominates,
# purchases are comparatively rare — this gives a realistic funnel shape and a
# conversion rate well under 1.0.
_WEIGHTS = {
    "page_view": 60,
    "session_start": 25,
    "add_to_cart": 10,
    "purchase": 5,
}

_WEIGHTED_POOL: List[str] = []
for _etype in EVENT_TYPES:
    _WEIGHTED_POOL.extend([_etype] * _WEIGHTS[_etype])


def _pick_type(rng: random.Random) -> str:
    """Pick an event type using the fixed weighted pool (deterministic)."""
    idx = rng.randrange(len(_WEIGHTED_POOL))
    return _WEIGHTED_POOL[idx]


def generate_batch(
    seed: int = 7,
    n: int = 100,
    start_ts: float = 1_700_000_000.0,
    step_seconds: float = 1.0,
) -> List[Dict]:
    """Generate a deterministic batch of ``n`` events.

    Events are evenly spaced ``step_seconds`` apart starting at ``start_ts``.
    Same (seed, n, start_ts, step_seconds) -> identical output. This is the
    function unit tests rely on for golden values.
    """
    rng = random.Random(seed)
    events: List[Dict] = []
    for i in range(n):
        etype = _pick_type(rng)
        user_n = rng.randrange(1, 21)        # 20 distinct users
        sess_n = rng.randrange(1, 11)        # 10 distinct sessions
        events.append(
            {
                "event_id": f"evt-{seed}-{i}",
                "user_id": f"user-{user_n}",
                "session_id": f"sess-{sess_n}",
                "event_type": etype,
                "event_ts": float(start_ts + i * step_seconds),
            }
        )
    return events


def stream_events(
    seed: int = 7,
    rate_per_sec: float = 5.0,
    burst_every: int = 0,
    burst_multiplier: int = 1,
) -> Iterator[Dict]:
    """Infinite, reproducible generator for the live producer.

    Each event is stamped with the *current* wall-clock time so the processor's
    tumbling windows line up with real "now". ``rate_per_sec`` controls pacing.

    ``burst_every`` / ``burst_multiplier`` let the producer optionally inject a
    high-volume burst (used to force the events_per_minute alert to fire). When
    ``burst_every`` is 0 no bursting happens.
    """
    rng = random.Random(seed)
    counter = 0
    base_interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0
    while True:
        in_burst = burst_every > 0 and (counter // burst_every) % 2 == 1
        emit = burst_multiplier if in_burst else 1
        for _ in range(emit):
            etype = _pick_type(rng)
            user_n = rng.randrange(1, 21)
            sess_n = rng.randrange(1, 11)
            yield {
                "event_id": f"evt-{seed}-{counter}",
                "user_id": f"user-{user_n}",
                "session_id": f"sess-{sess_n}",
                "event_type": etype,
                "event_ts": time.time(),
            }
            counter += 1
        if base_interval:
            time.sleep(base_interval)
