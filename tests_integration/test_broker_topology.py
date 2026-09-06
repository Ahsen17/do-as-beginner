"""Integration: RabbitMQ broker exposes the expected dab topology."""

import os

from kombu import Connection

AMQP_DSN = os.environ.get("DAB_AMQP_DSN", "amqp://dab:dab@127.0.0.1:5672/dab")
PREFIX = os.environ.get("DAB_QUEUE_PREFIX", "dab.tasks")
TIERS = ("urgent", "high", "default", "low")


def test_broker_exposes_full_topology() -> None:
    """Passive-declare each expected queue/exchange; missing ones raise."""

    with Connection(AMQP_DSN) as conn:
        channel = conn.channel()
        for exchange in (f"{PREFIX}.exchange", f"{PREFIX}.dlx"):
            channel.exchange_declare(exchange=exchange, type="direct", passive=True)
        for queue in [f"{PREFIX}.{tier}" for tier in TIERS] + [f"{PREFIX}.internal", f"{PREFIX}.dlq"]:
            channel.queue_declare(queue=queue, passive=True)
