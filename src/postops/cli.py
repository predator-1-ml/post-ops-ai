from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import github_intel
from .classify import triage
from .drafter import draft_reply
from .models import Kind, Status, load_post, save_post

STATE_DIR = Path("state")


def _state_path(post_id: str) -> Path:
    return STATE_DIR / f"{post_id}.json"


def _snippet(text: str, n: int = 62) -> str:
    one = " ".join(text.split())
    return one if len(one) <= n else one[: n - 1] + "…"


def cmd_triage(args: argparse.Namespace) -> int:
    post = triage(load_post(args.post))
    save_post(post, _state_path(post.id))
    print(f"post {post.id} · {len(post.comments)} comments · state -> {_state_path(post.id)}\n")
    print(f"{'id':<4} {'author':<20} {'kind':<12} {'status':<17} text")
    for c in post.comments:
        print(f"{c.id:<4} {c.author[:19]:<20} {c.kind.value:<12} {c.status.value:<17} {_snippet(c.text)}")
    n_exp = sum(c.kind is Kind.GITHUB_LINK for c in post.comments)
    print(f"\n{n_exp} comment(s) link a repo and need a local experiment before any reply.")
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    print(github_intel.to_markdown(github_intel.fetch_brief(args.repo)))
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    post = load_post(args.state)
    comment = post.comment(args.comment)
    if comment.kind is Kind.GITHUB_LINK and not args.evidence:
        print("refusing: this comment links a repo. Run the experiment first and pass --evidence <FINDINGS.md>.")
        return 2
    evidence = "\n\n".join(Path(p).read_text(encoding="utf-8") for p in args.evidence or [])
    d = draft_reply(post, comment, evidence)
    print(f"intent={d.intent} should_reply={d.should_reply}")
    if d.unverified_claims:
        print("unverified claims:", *d.unverified_claims, sep="\n  - ")
    if d.problems:
        print("problems:", *d.problems, sep="\n  - ")
    print("\n" + (d.reply or "(no reply recommended)"))
    if d.should_reply and not d.problems:
        comment.draft, comment.evidence, comment.status = d.reply, list(args.evidence or []), Status.DRAFTED
        save_post(post, args.state)
        print(f"\nsaved as draft on {comment.id}; nothing was posted.")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    """Render every comment with its draft so a human can approve, edit or drop each one."""
    post = load_post(args.state)
    out = [f"# Review: post {post.id}", "", f"{post.url}", ""]
    for c in post.comments:
        out += [f"## {c.id} · {c.author} · {c.kind.value} · {c.status.value}", ""]
        out += [f"> {line}" for line in c.text.splitlines()] + [""]
        if c.note:
            out += [f"_Note: {c.note}_", ""]
        out += [f"**Draft ({len(c.draft)} chars):**", "", c.draft, ""] if c.draft else ["_No draft._", ""]
    text = "\n".join(out)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="postops", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("triage", help="classify every comment on a captured post")
    t.add_argument("post", help="post JSON (see examples/)")
    t.set_defaults(fn=cmd_triage)

    b = sub.add_parser("brief", help="read-only brief of a linked GitHub repo (nothing is cloned or run)")
    b.add_argument("repo", help="owner/name")
    b.set_defaults(fn=cmd_brief)

    d = sub.add_parser("draft", help="draft a reply to one comment (needs ANTHROPIC_API_KEY or `ant auth login`)")
    d.add_argument("state", help="state/<post-id>.json written by triage")
    d.add_argument("comment", help="comment id, e.g. c12")
    d.add_argument("--evidence", nargs="*", help="files that back the reply, e.g. experiments/<slug>/FINDINGS.md")
    d.set_defaults(fn=cmd_draft)

    r = sub.add_parser("review", help="render all comments and drafts as markdown for approval")
    r.add_argument("state")
    r.add_argument("--out", help="write to this file instead of stdout")
    r.set_defaults(fn=cmd_review)

    args = p.parse_args(argv)
    # Commenter names and posts are not ASCII; the default Windows console codec (cp1252) would crash.
    sys.stdout.reconfigure(encoding="utf-8")
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
