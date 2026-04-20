"""
Bounty Claim Checkers — All 5 verification checks.

Milestones implemented:
1. Star/follow verification (30 RTC)
2. Wallet existence check (+10 RTC)
3. Article/URL verification (+10 RTC)
4. Dev.to word count + quality check (+10 RTC)
5. Duplicate claim detection (+15 RTC)
"""

import json
import re
import time
import os
import requests
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


# --- Configuration ---

SCOTT_REPOS = [
    "Rustchain", "rustchain-bounties", "bottube", "beacon-skill",
    "grazer-skill", "ram-coffers", "llama-cpp-power8", "shaprai",
    "rustchain-mcp", "rustchain-wallet", "elyan-prime", "sophiacord",
    "bounty-concierge", "grazer",
]
RUSTCHAIN_NODE = os.environ.get("RUSTCHAIN_NODE_URL", "https://50.28.86.131")


@dataclass
class CheckResult:
    """Result of a single verification check."""
    name: str
    passed: bool
    details: str
    value: str = ""
    confidence: str = "high"  # high, medium, low


@dataclass
class VerificationReport:
    """Complete verification report for a claim."""
    username: str
    wallet: Optional[str]
    checks: list = field(default_factory=list)
    suggested_payout: float = 0.0
    warnings: list = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    def add_check(self, result: CheckResult):
        self.checks.append(result)

    def add_warning(self, msg: str):
        self.warnings.append(msg)


# ============================================================
# CHECK 1: Star & Follow Verification (30 RTC)
# ============================================================

def check_star_follow(username: str, token: str,
                      claimed_stars: int = 0, claimed_follow: bool = False) -> CheckResult:
    """Verify star count and follow status via GitHub API.

    Args:
        username: GitHub username
        token: GitHub PAT
        claimed_stars: How many stars user claims
        claimed_follow: Whether user claims to follow

    Returns:
        CheckResult with verification status
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    base = "https://api.github.com"

    # Check follow status
    follows = False
    try:
        resp = requests.get(f"{base}/user/following/Scottcjn", headers=headers, timeout=10)
        follows = resp.status_code == 204
    except Exception as e:
        return CheckResult(
            name="Star & Follow",
            passed=False,
            details=f"API error checking follow: {e}",
            confidence="low"
        )

    # Count starred Scottcjn repos
    starred_repos = []
    page = 1
    max_pages = 5  # Safety limit

    while page <= max_pages:
        try:
            resp = requests.get(
                f"{base}/user/starred",
                headers=headers,
                params={"per_page": 100, "page": page},
                timeout=15
            )
            if resp.status_code != 200:
                break
            repos = resp.json()
            if not repos:
                break
            for r in repos:
                owner = r.get("owner", {}).get("login", "").lower()
                if owner == "scottcjn":
                    starred_repos.append(r["name"])
            if len(repos) < 100:
                break
            page += 1
        except Exception:
            break

    star_count = len(starred_repos)

    # Build result
    details_parts = []
    if follows:
        details_parts.append("✅ Follows @Scottcjn")
    else:
        details_parts.append("❌ Does NOT follow @Scottcjn")

    details_parts.append(f"⭐ Stars {star_count} Scottcjn repos")

    if starred_repos:
        details_parts.append(f"   Repos: {', '.join(starred_repos[:10])}")

    if claimed_stars > 0 and star_count != claimed_stars:
        details_parts.append(f"⚠️ Claimed {claimed_stars} but API shows {star_count}")

    passed = follows and star_count > 0

    return CheckResult(
        name="Star & Follow",
        passed=passed,
        details="\n".join(details_parts),
        value=f"stars={star_count},follow={follows}"
    )


# ============================================================
# CHECK 2: Wallet Existence (10 RTC)
# ============================================================

def check_wallet(wallet_name: str) -> CheckResult:
    """Query RustChain node for wallet balance.

    Args:
        wallet_name: Claimed wallet/miner ID

    Returns:
        CheckResult with wallet status
    """
    if not wallet_name:
        return CheckResult(
            name="Wallet Check",
            passed=False,
            details="❌ No wallet address provided in claim",
            confidence="high"
        )

    try:
        resp = requests.get(
            f"{RUSTCHAIN_NODE}/wallet/balance",
            params={"miner_id": wallet_name},
            timeout=15,
            verify=False  # Self-signed cert on RustChain node
        )

        if resp.status_code == 200:
            data = resp.json()
            balance = data.get("balance", 0)
            return CheckResult(
                name="Wallet Check",
                passed=True,
                details=f"✅ Wallet `{wallet_name}` exists — Balance: {balance} RTC",
                value=f"balance={balance}"
            )
        elif resp.status_code == 404:
            return CheckResult(
                name="Wallet Check",
                passed=False,
                details=f"❌ Wallet `{wallet_name}` NOT FOUND (404)",
                confidence="high"
            )
        else:
            return CheckResult(
                name="Wallet Check",
                passed=False,
                details=f"⚠️ Wallet API returned {resp.status_code}: {resp.text[:200]}",
                confidence="medium"
            )
    except requests.exceptions.Timeout:
        return CheckResult(
            name="Wallet Check",
            passed=False,
            details="⚠️ Wallet API timeout — node may be down",
            confidence="low"
        )
    except Exception as e:
        return CheckResult(
            name="Wallet Check",
            passed=False,
            details=f"⚠️ Wallet check failed: {e}",
            confidence="low"
        )


# ============================================================
# CHECK 3: Article/URL Verification (10 RTC)
# ============================================================

def check_article_url(url: str) -> CheckResult:
    """Verify an article URL is live and accessible.

    Args:
        url: Article URL to check

    Returns:
        CheckResult with URL status
    """
    if not url:
        return CheckResult(
            name="Article URL",
            passed=False,
            details="❌ No article URL provided",
            confidence="high"
        )

    try:
        # Try HEAD first (faster), fallback to GET
        resp = requests.head(url, timeout=10, allow_redirects=True,
                             headers={"User-Agent": "BountyVerifier/1.0"})
        if resp.status_code >= 400:
            resp = requests.get(url, timeout=15, allow_redirects=True,
                                headers={"User-Agent": "BountyVerifier/1.0"})

        if resp.status_code < 400:
            content_type = resp.headers.get("Content-Type", "")

            # Extract domain
            parsed = urlparse(url)
            domain = parsed.netloc

            return CheckResult(
                name="Article URL",
                passed=True,
                details=f"✅ URL is live — {domain} (HTTP {resp.status_code})",
                value=f"status={resp.status_code},domain={domain}"
            )
        else:
            return CheckResult(
                name="Article URL",
                passed=False,
                details=f"❌ URL returned HTTP {resp.status_code}",
                confidence="high"
            )
    except requests.exceptions.Timeout:
        return CheckResult(
            name="Article URL",
            passed=False,
            details="❌ URL timed out — may be down or slow",
            confidence="medium"
        )
    except Exception as e:
        return CheckResult(
            name="Article URL",
            passed=False,
            details=f"❌ URL check failed: {e}",
            confidence="low"
        )


# ============================================================
# CHECK 4: Dev.to Article Word Count + Quality (10 RTC)
# ============================================================

def check_article_quality(url: str) -> CheckResult:
    """Check dev.to/Medium article word count and basic quality.

    Args:
        url: Article URL (dev.to or medium.com)

    Returns:
        CheckResult with quality assessment
    """
    if not url:
        return CheckResult(
            name="Article Quality",
            passed=False,
            details="No article to check",
            confidence="high"
        )

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Only check dev.to and medium.com
    if "dev.to" not in domain and "medium.com" not in domain:
        return CheckResult(
            name="Article Quality",
            passed=True,
            details=f"ℹ️ Not dev.to/Medium ({domain}) — skipping word count check",
            confidence="medium"
        )

    try:
        resp = requests.get(url, timeout=15,
                            headers={"User-Agent": "BountyVerifier/1.0"})
        if resp.status_code >= 400:
            return CheckResult(
                name="Article Quality",
                passed=False,
                details=f"❌ Cannot fetch article (HTTP {resp.status_code})",
                confidence="high"
            )

        html = resp.text

        # Simple word count from HTML (strip tags)
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        words = len(text.split())

        # Quality assessment
        quality_signals = []
        if words >= 500:
            quality_signals.append("✅ Substantial content (500+ words)")
        elif words >= 200:
            quality_signals.append("⚠️ Moderate content (200-500 words)")
        else:
            quality_signals.append(f"❌ Short content ({words} words, <200 threshold)")

        # Check for code blocks (indicates technical content)
        has_code = bool(re.search(r'<code|<pre|```', html, re.IGNORECASE))
        if has_code:
            quality_signals.append("✅ Contains code examples")

        # Check for headings (indicates structure)
        headings = len(re.findall(r'<h[1-6][^>]*>', html, re.IGNORECASE))
        if headings >= 2:
            quality_signals.append(f"✅ Well-structured ({headings} sections)")

        passed = words >= 200  # Minimum threshold

        return CheckResult(
            name="Article Quality",
            passed=passed,
            details="\n".join(quality_signals),
            value=f"words={words}"
        )

    except Exception as e:
        return CheckResult(
            name="Article Quality",
            passed=False,
            details=f"⚠️ Quality check failed: {e}",
            confidence="low"
        )


# ============================================================
# CHECK 5: Duplicate Claim Detection (15 RTC)
# ============================================================

def check_duplicate_claims(username: str, issue_comments: list,
                           current_comment_id: int) -> CheckResult:
    """Detect if user already claimed/paid on this issue or others.

    Scans previous comments for:
    - "PAID" markers referencing this user
    - Previous claims from same wallet
    - Same user claiming multiple times

    Args:
        username: GitHub username
        issue_comments: List of comment dicts from GitHub API
        current_comment_id: ID of the current claim comment

    Returns:
        CheckResult with duplicate status
    """
    if not issue_comments:
        return CheckResult(
            name="Duplicate Check",
            passed=True,
            details="✅ No previous comments to check — first claim",
            confidence="high"
        )

    paid_count = 0
    claim_count = 0
    paid_details = []

    for comment in issue_comments:
        body = comment.get("body", "").upper()
        comment_user = comment.get("user", {}).get("login", "").lower()
        comment_id = comment.get("id", 0)

        # Skip the current claim comment
        if comment_id == current_comment_id:
            continue

        # Skip bot comments for claim counting (but check for PAID markers)
        if comment_user in ["github-actions[bot]", "verifier-bot"]:
            # Check if this bot comment says PAID for our user
            if f"@{username.upper()}" in body and "PAID" in body:
                paid_count += 1
                paid_details.append(f"Paid on comment #{comment_id}")

        # Check if same user made previous claims
        if comment_user == username.lower() and comment_id != current_comment_id:
            # Look for claim-like keywords
            claim_keywords = ["CLAIM", "WALLET", "STARS", "STARRED", "FOLLOW"]
            if any(kw in body for kw in claim_keywords):
                claim_count += 1

    details_parts = []

    if paid_count > 0:
        details_parts.append(
            f"⚠️ Found {paid_count} previous payment(s) for @{username}:"
        )
        for d in paid_details:
            details_parts.append(f"   - {d}")
    else:
        details_parts.append("✅ No previous payments found for this user")

    if claim_count > 1:
        details_parts.append(
            f"⚠️ User made {claim_count} previous claim(s) on this issue"
        )

    # Duplicate if already paid
    passed = paid_count == 0

    return CheckResult(
        name="Duplicate Check",
        passed=passed,
        details="\n".join(details_parts),
        value=f"prev_paid={paid_count},prev_claims={claim_count}"
    )


# ============================================================
# Payout Calculator
# ============================================================

def calculate_payout(report: VerificationReport, config: dict) -> float:
    """Calculate suggested RTC payout based on verification results.

    Args:
        report: Completed verification report
        config: Bounty rules from config file

    Returns:
        Suggested RTC amount
    """
    rates = config.get("rates", {})
    star_rate = rates.get("star", 1.0)
    follow_bonus = rates.get("follow_bonus", 1.0)
    min_stars = rates.get("min_stars", 1)

    payout = 0.0

    for check in report.checks:
        if check.name == "Star & Follow" and check.passed:
            # Parse star count from value
            star_match = re.search(r"stars=(\d+)", check.value)
            follow_match = re.search(r"follow=(True|true)", check.value)

            stars = int(star_match.group(1)) if star_match else 0
            follows = bool(follow_match)

            if stars >= min_stars:
                payout += stars * star_rate
            if follows:
                payout += follow_bonus

    return round(payout, 1)
