"""
Bounty Verifier — Main orchestrator.

Entry point that ties together parsing, checking, and reporting.
Designed to run as a GitHub Action triggered by issue_comment events.
"""

import os
import sys
import json
import yaml
import requests
import urllib3

# Suppress SSL warnings for self-signed RustChain cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from parser import parse_claim_comment, ClaimData
from checkers import (
    check_star_follow,
    check_wallet,
    check_article_url,
    check_article_quality,
    check_duplicate_claims,
    calculate_payout,
    VerificationReport,
)
from reporter import generate_report


# --- Trigger Keywords ---
CLAIM_KEYWORDS = ["claiming", "wallet:", "stars:", "starred", "github:", "bounty claim"]


def is_claim_comment(body: str) -> bool:
    """Check if a comment looks like a bounty claim."""
    lower = body.lower()
    return any(kw in lower for kw in CLAIM_KEYWORDS)


def load_config(config_path: str = None) -> dict:
    """Load bounty rules from YAML config."""
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config", "bounty-rules.yml"
        )

    defaults = {
        "rates": {
            "star": 1.0,
            "follow_bonus": 1.0,
            "min_stars": 1,
        },
        "target_owner": "Scottcjn",
        "trigger_keywords": CLAIM_KEYWORDS,
    }

    try:
        with open(config_path) as f:
            user_config = yaml.safe_load(f) or {}
        defaults.update(user_config)
    except FileNotFoundError:
        print(f"[INFO] No config at {config_path}, using defaults")

    return defaults


def get_issue_comments(owner: str, repo: str, issue_number: int,
                       token: str) -> list:
    """Fetch all comments on a GitHub issue."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"

    comments = []
    page = 1
    while page <= 10:  # Max 10 pages
        resp = requests.get(url, headers=headers,
                           params={"per_page": 100, "page": page},
                           timeout=15)
        if resp.status_code != 200:
            break
        batch = resp.json()
        if not batch:
            break
        comments.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    return comments


def post_comment(owner: str, repo: str, issue_number: int,
                 token: str, body: str) -> bool:
    """Post a comment on a GitHub issue."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
    resp = requests.post(url, headers=headers,
                        json={"body": body},
                        timeout=15)
    return resp.status_code == 201


def run_verification(owner: str, repo: str, issue_number: int,
                     comment_body: str, comment_user: str,
                     comment_id: int, comment_created: str,
                     token: str, config: dict):
    """Run full verification pipeline and post results.

    Args:
        owner: Repository owner
        repo: Repository name
        issue_number: Issue number
        comment_body: Raw comment text
        comment_user: Commenter's GitHub username
        comment_id: Comment ID
        comment_created: Comment creation timestamp
        token: GitHub PAT
        config: Bounty rules config
    """
    print(f"[VERIFY] Processing claim from @{comment_user} on {owner}/{repo}#{issue_number}")

    # Parse claim
    claim = parse_claim_comment(
        comment_body,
        username=comment_user,
        comment_id=comment_id,
        created_at=comment_created,
    )

    if not claim.is_valid_claim:
        print("[SKIP] Comment doesn't look like a valid claim")
        return

    print(f"[CLAIM] wallet={claim.wallet}, stars={claim.claimed_stars}, "
          f"follow={claim.claimed_follow}, urls={len(claim.article_urls)}")

    # Build verification report
    report = VerificationReport(
        username=comment_user,
        wallet=claim.wallet,
    )

    # CHECK 1: Star & Follow
    print("[CHECK 1/5] Star & Follow verification...")
    star_result = check_star_follow(
        comment_user, token,
        claimed_stars=claim.claimed_stars,
        claimed_follow=claim.claimed_follow,
    )
    report.add_check(star_result)

    # CHECK 2: Wallet existence
    print("[CHECK 2/5] Wallet existence check...")
    wallet_result = check_wallet(claim.wallet)
    report.add_check(wallet_result)

    # CHECK 3 & 4: Article verification
    if claim.article_urls:
        for url in claim.article_urls:
            print(f"[CHECK 3/5] Article URL verification: {url}")
            url_result = check_article_url(url)
            report.add_check(url_result)

            print(f"[CHECK 4/5] Article quality check: {url}")
            quality_result = check_article_quality(url)
            report.add_check(quality_result)
    else:
        report.add_check(VerificationResult(
            name="Article URL",
            passed=True,
            details="ℹ️ No article URLs in claim — skipping",
            confidence="high"
        ))

    # CHECK 5: Duplicate detection
    print("[CHECK 5/5] Duplicate claim detection...")
    all_comments = get_issue_comments(owner, repo, issue_number, token)
    dupe_result = check_duplicate_claims(comment_user, all_comments, comment_id)
    report.add_check(dupe_result)

    # Calculate payout
    report.suggested_payout = calculate_payout(report, config)

    # Generate and post report
    report_md = generate_report(report)
    print(f"\n[REPORT]\n{report_md}\n")

    # Post as comment
    success = post_comment(owner, repo, issue_number, token, report_md)
    if success:
        print("[OK] Verification report posted!")
    else:
        print("[ERROR] Failed to post report comment")
        # Fallback: output to stdout
        print(report_md)

    # Write summary for GitHub Actions
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write(f"\n## Verification for @{comment_user}\n")
            f.write(f"- Checks passed: {report.pass_count}/{len(report.checks)}\n")
            f.write(f"- Suggested payout: {report.suggested_payout} RTC\n")


def main():
    """Main entry point for GitHub Actions.

    Reads environment variables set by the workflow and processes
    the triggering comment.
    """
    # GitHub Actions environment
    token = os.environ.get("GITHUB_TOKEN", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")

    if not token:
        print("[ERROR] GITHUB_TOKEN not set")
        sys.exit(1)

    if not event_path:
        # Manual/test mode
        print("[INFO] No GITHUB_EVENT_PATH — running in test mode")
        config = load_config()
        test_comment = os.environ.get("TEST_COMMENT", "")
        if test_comment:
            print(f"[TEST] Would process: {test_comment[:200]}")
        else:
            print("[TEST] Set TEST_COMMENT env var to test parsing")
        return

    # Load webhook event
    with open(event_path) as f:
        event = json.load(f)

    # Only process issue_comment events
    action = event.get("action", "")
    if action != "created":
        print(f"[SKIP] Action is '{action}', not 'created'")
        return

    comment = event.get("comment", {})
    issue = event.get("issue", {})
    repository = event.get("repository", {})

    comment_body = comment.get("body", "")
    comment_user = comment.get("user", {}).get("login", "")
    comment_id = comment.get("id", 0)
    comment_created = comment.get("created_at", "")

    issue_number = issue.get("number", 0)

    owner = repository.get("owner", {}).get("login", "")
    repo = repository.get("name", "")

    # Check trigger
    if not is_claim_comment(comment_body):
        print("[SKIP] Comment doesn't contain claim keywords")
        return

    # Load config
    config = load_config()

    # Run verification
    run_verification(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        comment_body=comment_body,
        comment_user=comment_user,
        comment_id=comment_id,
        comment_created=comment_created,
        token=token,
        config=config,
    )


if __name__ == "__main__":
    main()
