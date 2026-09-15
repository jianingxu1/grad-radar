from types import SimpleNamespace
from typing import cast
from uuid import uuid4

from app.database.models import JobPosting
from app.services.notifications import TELEGRAM_MESSAGE_LIMIT, _message_batches


def test_message_batches_split_an_oversized_single_job() -> None:
    job = SimpleNamespace(
        id=uuid4(),
        company_name="Company",
        title="A" * TELEGRAM_MESSAGE_LIMIT,
        location="Remote, USA",
        apply_url="https://jobs.example.com/apply",
    )

    batches = _message_batches([cast(JobPosting, job)])

    assert len(batches) > 1
    assert all(len(message) <= TELEGRAM_MESSAGE_LIMIT for message, _ in batches)
    assert all(jobs == [job] for _, jobs in batches)
