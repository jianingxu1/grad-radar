from types import SimpleNamespace
from typing import cast
from uuid import uuid4

from app.database.models import JobPosting
from app.services.notifications import TELEGRAM_MESSAGE_LIMIT, _message_batches


def test_message_batches_truncate_an_oversized_single_job() -> None:
    job = SimpleNamespace(
        id=uuid4(),
        company_name="Company",
        title="A" * TELEGRAM_MESSAGE_LIMIT,
        location="Remote, USA",
        apply_url="https://jobs.example.com/apply",
    )

    batches = _message_batches([cast(JobPosting, job)])

    assert len(batches) == 1
    assert all(len(message) <= TELEGRAM_MESSAGE_LIMIT for message, _ in batches)
    assert batches[0][1] == [job]
    assert "…" in batches[0][0]


def test_message_batches_render_safe_telegram_html() -> None:
    job = SimpleNamespace(
        id=uuid4(),
        company_name='<a href="https://company.example"><strong>Pay & Co</strong></a>',
        title="Engineer <Platform>",
        location="San Jose, CA & Remote",
        apply_url="https://jobs.example.com/apply?source=grad&role=engineer",
    )

    message, jobs = _message_batches([cast(JobPosting, job)])[0]

    assert jobs == [job]
    assert message == (
        "🔔 1 new job found\n\n"
        "<b>Pay &amp; Co</b>\n"
        "💼 Engineer &lt;Platform&gt;\n"
        "📍 San Jose, CA &amp; Remote\n"
        '🔗 <a href="https://jobs.example.com/apply?source=grad&amp;role=engineer">Apply</a>'
    )


def test_message_batches_include_count_and_separator() -> None:
    jobs = [
        SimpleNamespace(
            id=uuid4(),
            company_name="RTX",
            title="System Integration Software Engineer I",
            location="Cedar Rapids, IA",
            apply_url="https://jobs.example.com/rtx",
        ),
        SimpleNamespace(
            id=uuid4(),
            company_name="Headlands Tech Holdings",
            title="C++ Software Developer, New Grad",
            location="Chicago, IL",
            apply_url="https://jobs.example.com/headlands",
        ),
    ]

    message, message_jobs = _message_batches(cast(list[JobPosting], jobs))[0]

    assert message_jobs == jobs
    assert message.startswith("🔔 2 new jobs found\n\n<b>RTX</b>")
    assert "\n\n──────────────\n\n<b>Headlands Tech Holdings</b>" in message
