"""Review a pull request with an LLM and post the result as one PR comment.

Runs in GitHub Actions (see .github/workflows/pr-review.yml) and needs these
environment variables: GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER and the
AZURE_OPENAI_* settings.
"""

import os
import sys

import httpx

from agent.llm import ConfigError, create_client

GITHUB_API = "https://api.github.com"
MAX_DIFF_CHARS = 60_000
COMMENT_MARKER = "<!-- ai-pr-review -->"

REVIEW_PROMPT = (
    "You are a senior software engineer reviewing a pull request. Based on the "
    "diff, write a short summary of what the change does, followed by a list of "
    "concrete improvement suggestions (bugs, readability, tests, security). "
    "If the change looks good, say so. Keep it brief."
)


def truncate_diff(diff: str, limit: int = MAX_DIFF_CHARS) -> tuple[str, bool]:
    """Shorten very large diffs. Returns the diff and whether it was cut."""
    if len(diff) <= limit:
        return diff, False
    return diff[:limit], True


def build_comment(review: str, truncated: bool) -> str:
    note = (
        "\n\n_Note: the diff was too long and was shortened before the review._"
        if truncated
        else ""
    )
    return f"{COMMENT_MARKER}\n## AI review\n\n{review}{note}"


def find_existing_comment(comments: list[dict]) -> int | None:
    """Return the ID of an earlier review comment by this bot, if there is one."""
    for comment in comments:
        if COMMENT_MARKER in (comment.get("body") or ""):
            return comment["id"]
    return None


def github_client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=GITHUB_API,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )


def get_diff(gh: httpx.Client, repo: str, pr_number: int) -> str:
    response = gh.get(
        f"/repos/{repo}/pulls/{pr_number}",
        headers={"Accept": "application/vnd.github.diff"},
    )
    response.raise_for_status()
    return response.text


def review_diff(diff: str) -> str:
    client, model = create_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": f"Review this diff:\n\n{diff}"},
        ],
    )
    return response.choices[0].message.content or "The model returned no review."


def post_or_update_comment(
    gh: httpx.Client, repo: str, pr_number: int, body: str
) -> None:
    """Keep a single review comment per PR: update it if it exists."""
    response = gh.get(
        f"/repos/{repo}/issues/{pr_number}/comments", params={"per_page": 100}
    )
    response.raise_for_status()
    existing_id = find_existing_comment(response.json())

    if existing_id is None:
        response = gh.post(
            f"/repos/{repo}/issues/{pr_number}/comments", json={"body": body}
        )
    else:
        response = gh.patch(
            f"/repos/{repo}/issues/comments/{existing_id}", json={"body": body}
        )
    response.raise_for_status()


def main() -> int:
    try:
        token = os.environ["GITHUB_TOKEN"]
        repo = os.environ["GITHUB_REPOSITORY"]
        pr_number = int(os.environ["PR_NUMBER"])
    except (KeyError, ValueError) as exc:
        print(f"Missing or invalid GitHub setting: {exc}")
        return 1

    with github_client(token) as gh:
        diff, truncated = truncate_diff(get_diff(gh, repo, pr_number))
        if not diff.strip():
            review = "This pull request has no code changes to review."
        else:
            try:
                review = review_diff(diff)
            except ConfigError as exc:
                print(exc)
                return 1
        post_or_update_comment(gh, repo, pr_number, build_comment(review, truncated))

    print(f"Posted the review on PR #{pr_number}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
