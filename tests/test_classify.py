from pathlib import Path

import pytest

from postops.classify import github_repos, triage
from postops.models import Kind, Status, load_post

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "sample-post.json"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("see https://github.com/example-org/gateway-benchmark/", ["example-org/gateway-benchmark"]),
        ("github.com/foo/bar.git is mine", ["foo/bar"]),
        ("https://github.com/foo/bar/blob/main/x.py and https://github.com/foo/bar", ["foo/bar"]),
        ("https://github.com/a/b, https://github.com/c/d.", ["a/b", "c/d"]),
        ("https://github.com/features/copilot", []),
        ("no links here, just github the company", []),
    ],
)
def test_github_repos(text, expected):
    assert github_repos(text) == expected


def test_triage_fixture():
    post = triage(load_post(FIXTURE))
    assert len(post.comments) == 14
    by_id = {c.id: c for c in post.comments}

    assert by_id["c08"].kind is Kind.GITHUB_LINK
    assert by_id["c08"].status is Status.NEEDS_EXPERIMENT
    assert by_id["c08"].repos == ["example-org/gateway-benchmark"]

    # The author already answered the first commenter, so the bot must not draft a second reply.
    assert by_id["c01"].status is Status.ALREADY_REPLIED

    others = [c for c in post.comments if c.id not in ("c01", "c08")]
    assert all(c.kind is Kind.NORMAL and c.status is Status.NEW for c in others)


def test_triage_is_idempotent_and_keeps_later_states():
    post = triage(load_post(FIXTURE))
    post.comment("c12").status = Status.DRAFTED
    triage(post)
    assert post.comment("c12").status is Status.DRAFTED
