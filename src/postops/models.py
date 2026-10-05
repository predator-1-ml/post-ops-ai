from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


class Kind(str, Enum):
    NORMAL = "normal"
    GITHUB_LINK = "github_link"


class Status(str, Enum):
    NEW = "new"
    ALREADY_REPLIED = "already_replied"
    NEEDS_EXPERIMENT = "needs_experiment"
    DRAFTED = "drafted"
    APPROVED = "approved"
    POSTED = "posted"
    SKIPPED = "skipped"


@dataclass
class Reply:
    author: str
    text: str
    is_post_author: bool = False


@dataclass
class Comment:
    id: str
    author: str
    text: str
    headline: str = ""
    age: str = ""
    truncated: bool = False
    replies: list[Reply] = field(default_factory=list)
    kind: Kind = Kind.NORMAL
    status: Status = Status.NEW
    repos: list[str] = field(default_factory=list)  # "owner/name" found in the comment
    draft: str = ""
    note: str = ""  # reviewer-facing: why this draft, or why there is none ("like only")
    evidence: list[str] = field(default_factory=list)  # repo-relative paths backing the draft


@dataclass
class Post:
    id: str
    url: str
    author: str
    text: str
    captured_at: str = ""
    comments: list[Comment] = field(default_factory=list)

    def comment(self, comment_id: str) -> Comment:
        for c in self.comments:
            if c.id == comment_id:
                return c
        raise KeyError(f"no comment {comment_id!r} in post {self.id}")


def load_post(path: str | Path) -> Post:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    comments = []
    for c in raw.get("comments", []):
        c = dict(c)
        c["replies"] = [Reply(**r) for r in c.get("replies", [])]
        c["kind"] = Kind(c.get("kind", Kind.NORMAL))
        c["status"] = Status(c.get("status", Status.NEW))
        comments.append(Comment(**c))
    return Post(**{**raw, "comments": comments})


def save_post(post: Post, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(post), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
