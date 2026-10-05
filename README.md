# post-ops-ai

Reply assistant for LinkedIn comment threads. It reads a post and its comments, sorts the comments,
drafts replies in a fixed opinion standard, and, when a commenter pushes back with a GitHub link,
holds the reply until we have reproduced their claim locally and published the findings.

It drafts. A human approves and posts. See [Safety](#safety).

## Comment types

| Kind | Example | What happens |
|---|---|---|
| `normal` | a question, a challenge, agreement | Draft a reply from [`persona/opinion_standard.md`](persona/opinion_standard.md). Low-signal comments ("Nice!") get a like or one line. |
| `github_link` | "my benchmark is here: github.com/…" | Read the repo read-only (`postops brief`), reproduce the claim under `experiments/<slug>/`, push results to this repo, then draft a reply that cites them. `postops draft` refuses until `--evidence` is given. |

Status flow: `new` / `already_replied` / `needs_experiment` → `drafted` → `approved` → `posted`.
A comment the post author already answered is never drafted again.

## Use

```bash
pip install -e ".[dev]"
python -m postops triage examples/sample-post.json   # -> state/<post-id>.json
python -m postops brief owner/repo                                     # read-only brief of a linked repo
python -m postops draft state/<post-id>.json c12                       # needs ANTHROPIC_API_KEY or `ant auth login`
python -m postops draft state/<post-id>.json c08 --evidence experiments/<slug>/FINDINGS.md
python -m postops review state/<post-id>.json --out state/review.md   # read, edit, approve
pytest
```

Capturing a post is currently done in a Claude in Chrome session: open the post, sort by
"Most recent", expand "… more" and reply threads, save the text as JSON (schema: `examples/`).
Comments keep arriving, so re-capture and re-run `triage`; existing statuses are preserved.

## Layout

```
src/postops/classify.py      kind + status from comment text and replies (pure)
src/postops/github_intel.py  read-only GitHub API intake; flags files to review before running
src/postops/drafter.py       Claude call, untrusted-input fencing, draft validation
src/postops/cli.py           triage | brief | draft | review
persona/                     the opinion standard every draft is held to
experiments/<slug>/          one folder per GitHub-link claim: harness, results/, FINDINGS.md
examples/                    synthetic post (14 comments, same shape as a real thread) used by the tests
```

## Safety

- **Nothing posts automatically.** There is no publish command. Posting is a separate, explicit step.
- **Comment text is untrusted.** It is fenced in the prompt, the model is told never to follow it, and drafts
  are validated: ≤1,250 characters and links only to our repo or `docs.litellm.ai`
  (override with `POSTOPS_ALLOWED_URLS`).
- **Linked repos are untrusted.** They are read through the API, never cloned or run by the bot. Files that
  address coding agents (`AGENTS.md`, `CLAUDE.md`, …) are listed and ignored. Anything executable is reviewed
  by a person before an experiment runs it, and experiments run in containers or throwaway venvs.
- **Automating LinkedIn itself** (scripted clicking, scraping at volume) is against LinkedIn's terms and risks the
  account. Capture and post stay human-supervised.

## Status

v0. Verified: the classifier and drafter request shape (unit tests with a fake client). Not yet verified: the drafter
against the live API, and any end-to-end posting.
