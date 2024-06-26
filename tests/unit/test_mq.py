#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

"""The unit tests for the mq module."""
import secrets
from unittest.mock import MagicMock

import pytest
from kombu import Connection
from kombu.exceptions import OperationalError

from webhook_router import mq
from webhook_router.parse import Job, JobStatus

IN_MEMORY_URI = "memory://"


@pytest.fixture(name="in_memory_mq")
def use_in_memory_mq(monkeypatch: pytest.MonkeyPatch):
    """Use the in-memory MQ for testing."""
    monkeypatch.setattr(mq, "MONGODB_DB_CONNECT_STR", IN_MEMORY_URI)


@pytest.mark.usefixtures("in_memory_mq")
def test_add_job_to_queue():
    """
    arrange: a job and a flavor
    act: add the job to the queue
    assert: the job is added to the queue
    """
    flavor = secrets.token_hex(16)
    labels = [secrets.token_hex(16), secrets.token_hex(16)]
    # mypy: does not recognize that run_url can be passed as a string
    job = Job(labels=labels, status=JobStatus.QUEUED, run_url="http://example.com")  # type: ignore
    mq.add_job_to_queue(job, flavor)

    with Connection(IN_MEMORY_URI) as conn:
        simple_queue = conn.SimpleQueue(flavor)

        msg = simple_queue.get(block=True, timeout=1)
        assert msg.payload == job.json()
        simple_queue.close()


@pytest.mark.usefixtures("in_memory_mq")
def test_can_connect():
    """
    arrange: in memory MQ setup
    act: call can_connect
    assert: the result is True
    """
    assert mq.can_connect() is True


def test_cannot_connect(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: mock ensure_connection to raise an error
    act: call can_connect
    assert: the result is False
    """
    monkeypatch.setattr(Connection, "ensure_connection", MagicMock(side_effect=OperationalError))
    assert mq.can_connect() is False
