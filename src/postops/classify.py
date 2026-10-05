from __future__ import annotations

import re

from .models import Comment, Kind, Post, Status

# Matches github.com/<owner>/<repo>, with or without a scheme. Deeper paths (/tree/..., /blob/...)
# and trailing punctuation are ignored; only the repo identity matters.
_REPO_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9._-]+)",
    re.IGNORECASE,
)

# github.com/<reserved>/... are site pages, not repositories.
_RESERVED_OWNERS = {
    "features", "sponsors", "orgs", "topics", "marketplace", "settings", "login", "about",
    "pricing", "enterprise", "collections", "explore", "trending", "security", "readme",
}


def github_repos(text: str) -> list[str]:
    """Distinct "owner/repo" slugs mentioned in text, in order of first appearance."""
    seen: list[str] = []
    for owner, repo in _REPO_RE.findall(text):
        if owner.lower() in _RESERVED_OWNERS:
            continue
        repo = repo.removesuffix(".git").rstrip(".")
        slug = f"{owner}/{repo}"
        if repo and slug.lower() not in (s.lower() for s in seen):
            seen.append(slug)
    return seen


def classify(comment: Comment) -> Comment:
    """Set kind, status and repos on a comment. Pure: depends only on the comment itself."""
    comment.repos = github_repos(comment.text)
    comment.kind = Kind.GITHUB_LINK if comment.repos else Kind.NORMAL
    if comment.status in (Status.NEW, Status.NEEDS_EXPERIMENT, Status.ALREADY_REPLIED):
        if any(r.is_post_author for r in comment.replies):
            comment.status = Status.ALREADY_REPLIED
        elif comment.kind is Kind.GITHUB_LINK:
            comment.status = Status.NEEDS_EXPERIMENT
        else:
            comment.status = Status.NEW
    return comment


def triage(post: Post) -> Post:
    for c in post.comments:
        classify(c)
    return post
