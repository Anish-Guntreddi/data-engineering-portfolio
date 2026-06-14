"""Producer: emit synthetic events to the Redpanda/Kafka topic 'events'.

Runtime service (containerized only). Uses confluent-kafka. The event payloads
come from the PURE ``streampulse.events.stream_events`` generator so the same
deterministic schema/logic is shared with the unit tests.

Environment
-----------
KAFKA_BOOTSTRAP   broker bootstrap servers (default redpanda:9092)
EVENTS_TOPIC      topic name (default "events")
PRODUCE_RATE      events per second (default 8)
PRODUCER_SEED     RNG seed for reproducibility (default 7)
BURST_EVERY       emit a burst every N events (default 50; 0 disables)
BURST_MULTIPLIER  events emitted per tick during a burst (default 12)

The default burst settings deliberately push events_per_minute well above the
alert threshold so ``make e2e`` reliably produces an alert.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time

from confluent_kafka import Producer

# Support running as a module (-m streampulse.producer.main) or as a script.
try:
    from streampulse.events import stream_events
except ModuleNotFoundError:  # pragma: no cover - container path fallback
    sys.path.insert(0, "/app")
    from streampulse.events import stream_events


_RUNNING = True


def _handle_sigterm(signum, frame):  # pragma: no cover - signal handler
    global _RUNNING
    _RUNNING = False


def _delivery_report(err, msg):  # pragma: no cover - kafka callback
    if err is not None:
        print(f"[producer] delivery failed: {err}", flush=True)


def main() -> int:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
    topic = os.getenv("EVENTS_TOPIC", "events")
    rate = float(os.getenv("PRODUCE_RATE", "8"))
    seed = int(os.getenv("PRODUCER_SEED", "7"))
    burst_every = int(os.getenv("BURST_EVERY", "50"))
    burst_multiplier = int(os.getenv("BURST_MULTIPLIER", "12"))

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    producer = Producer(
        {
            "bootstrap.servers": bootstrap,
            "client.id": "streampulse-producer",
            "linger.ms": 50,
        }
    )

    print(
        f"[producer] bootstrap={bootstrap} topic={topic} rate={rate}/s "
        f"seed={seed} burst_every={burst_every}x{burst_multiplier}",
        flush=True,
    )

    gen = stream_events(
        seed=seed,
        rate_per_sec=rate,
        burst_every=burst_every,
        burst_multiplier=burst_multiplier,
    )

    sent = 0
    last_log = time.time()
    for event in gen:
        if not _RUNNING:
            break
        payload = json.dumps(event).encode("utf-8")
        key = event["session_id"].encode("utf-8")
        try:
            producer.produce(topic, key=key, value=payload, callback=_delivery_report)
        except BufferError:
            producer.poll(0.5)
            producer.produce(topic, key=key, value=payload, callback=_delivery_report)
        producer.poll(0)
        sent += 1
        now = time.time()
        if now - last_log >= 5.0:
            print(f"[producer] sent={sent}", flush=True)
            last_log = now

    producer.flush(10)
    print(f"[producer] shutting down, total sent={sent}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
