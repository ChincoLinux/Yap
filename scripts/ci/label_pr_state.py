#!/usr/bin/env python3
"""Auto-assign PR state labels based on CI check results and human review status.

Adapted from os-santiago/homedir for ChincoLinux/Yap.

Labels:
  pr:draft             — PR is draft
  pr:checks-pending    — CI checks still running
  pr:checks-failed     — CI checks failed
  pr:needs-review      — CI passed, waiting for human review
  pr:changes-requested — human reviewer requested changes
  pr:approved          — human approval received (meets threshold)
  pr:merged            — PR was merged
  pr:blocked           — merge conflict or other blocker

Counts HUMAN approvals only (bots are ignored). Per AGENTS.md §3, the
yap-reviewer bot only posts comments and never approves, so bot reviews
are correctly excluded from the approval count.
"""

import os
import sys

try:
    from github import Github, Auth
except ImportError:
    print("ERROR: PyGithub not installed. Run: pip install PyGithub", file=sys.stderr)
    sys.exit(1)

# ─── pr:* state labels ─────────────────────────────────────────────────
LABEL_DRAFT = "pr:draft"
LABEL_CHECKS_PENDING = "pr:checks-pending"
LABEL_CHECKS_FAILED = "pr:checks-failed"
LABEL_NEEDS_REVIEW = "pr:needs-review"
LABEL_CHANGES_REQUESTED = "pr:changes-requested"
LABEL_APPROVED = "pr:approved"
LABEL_MERGED = "pr:merged"
LABEL_BLOCKED = "pr:blocked"

# All state labels this script manages (mutually exclusive)
STATE_LABELS = {
    LABEL_DRAFT, LABEL_CHECKS_PENDING, LABEL_CHECKS_FAILED,
    LABEL_NEEDS_REVIEW, LABEL_CHANGES_REQUESTED, LABEL_APPROVED,
    LABEL_MERGED, LABEL_BLOCKED,
}

# Required human approvals (Yap uses 1 per branch protection config)
DEFAULT_REQUIRED_APPROVALS = 1

# Bot users whose reviews do NOT count toward approval
BOT_REVIEWERS = {
    "github-actions[bot]", "dependabot[bot]", "copilot-pull-request-reviewer",
    "coderabbitai", "github-advanced-security[bot]", "github-openai-bot",
    "semantic-release-bot", "renovate-bot", "allcontributors[bot]",
}


def is_bot_reviewer(login: str) -> bool:
    """Check if a reviewer login is a bot."""
    if not login:
        return True
    if login in BOT_REVIEWERS:
        return True
    return login.endswith("[bot]") or login.endswith("-bot") or login.endswith("-ai")


def count_human_approvals(pr) -> tuple:
    """Count unique human approvals and detect changes-requested.

    Returns (approval_count, has_changes_requested).
    Uses the latest review per user (GitHub review semantics).
    """
    reviews = pr.get_reviews()
    if reviews.totalCount == 0:
        return 0, False

    # Build a map of reviewer → latest review state
    latest_by_user = {}
    for review in reviews:
        login = review.user.login if review.user else ""
        if is_bot_reviewer(login):
            continue
        if review.state in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest_by_user[login] = review.state

    approval_count = sum(1 for state in latest_by_user.values() if state == "APPROVED")
    has_changes_requested = any(
        state == "CHANGES_REQUESTED" for state in latest_by_user.values()
    )
    return approval_count, has_changes_requested


def get_ci_status(pr) -> str:
    """Determine CI check status.

    Returns 'pending', 'failed', or 'passed'.
    """
    commits = pr.get_commits()
    if commits.totalCount == 0:
        return "pending"

    last_commit = commits[commits.totalCount - 1]
    check_runs = last_commit.get_check_runs()
    if check_runs.totalCount == 0:
        return "pending"

    has_pending = False
    for run in check_runs:
        if run.status != "completed":
            has_pending = True
            continue
        # Skip advisory workflows (auto-merge, pr-review bot, board-sync)
        if run.name in ("enable-auto-merge", "A-Dev Hardness Review",
                        "add-to-project", "Auto-add to Roadmap Project"):
            continue
        if run.conclusion in ("failure", "cancelled", "timed_out"):
            return "failed"

    return "pending" if has_pending else "passed"


def determine_label(pr) -> str:
    """Determine the correct state label for a PR."""
    if pr.is_merged:
        return LABEL_MERGED

    if pr.draft:
        return LABEL_DRAFT

    # Check for merge conflicts
    if pr.mergeable is False:
        return LABEL_BLOCKED

    ci_status = get_ci_status(pr)
    if ci_status == "pending":
        return LABEL_CHECKS_PENDING
    if ci_status == "failed":
        return LABEL_CHECKS_FAILED

    # CI passed — check review status
    approval_count, has_changes = count_human_approvals(pr)

    if has_changes:
        return LABEL_CHANGES_REQUESTED

    if approval_count >= DEFAULT_REQUIRED_APPROVALS:
        return LABEL_APPROVED

    return LABEL_NEEDS_REVIEW


def apply_label(pr, target_label: str):
    """Apply the target state label, removing any other state labels."""
    current_labels = [label.name for label in pr.get_labels()]
    labels_to_remove = [l for l in current_labels if l in STATE_LABELS and l != target_label]

    for label in labels_to_remove:
        try:
            pr.remove_from_labels(label)
            print(f"  Removed label: {label}")
        except Exception as e:
            print(f"  WARNING: Could not remove label {label}: {e}", file=sys.stderr)

    if target_label not in current_labels:
        try:
            pr.add_to_labels(target_label)
            print(f"  Added label: {target_label}")
        except Exception as e:
            # Label might not exist yet — try to create it
            try:
                repo = pr.base.repo
                repo.create_label(
                    name=target_label,
                    color="ededed",
                    description="PR state (auto-managed by label_pr_state.py)",
                )
                pr.add_to_labels(target_label)
                print(f"  Created and added label: {target_label}")
            except Exception as e2:
                print(f"  WARNING: Could not add label {target_label}: {e2}", file=sys.stderr)
    else:
        print(f"  Label already set: {target_label}")


def main():
    github_token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("REPOSITORY")
    pr_number = os.environ.get("PR_NUMBER")

    if not all([github_token, repository]):
        print("ERROR: Missing required environment variables (GITHUB_TOKEN, REPOSITORY)", file=sys.stderr)
        sys.exit(1)

    github = Github(auth=Auth.Token(github_token))
    repo = github.get_repo(repository)

    if pr_number == "all" or not pr_number:
        # Label all open PRs
        prs = repo.get_pulls(state="open")
        for pr in prs:
            print(f"\nPR #{pr.number}: {pr.title}")
            label = determine_label(pr)
            print(f"  → {label}")
            apply_label(pr, label)
    else:
        pr = repo.get_pull(int(pr_number))
        print(f"\nPR #{pr.number}: {pr.title}")
        label = determine_label(pr)
        print(f"  → {label}")
        apply_label(pr, label)

    print("\nPR state labeling complete.")


if __name__ == "__main__":
    main()
