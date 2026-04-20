"""
Bounty Claim Parser — Extracts claim data from GitHub issue comments.

Parses comments for structured claim information:
- GitHub username (from comment author or explicit field)
- Claimed star count
- Claimed follow status
- Wallet address
- Article/URL proofs
"""

import re
import json
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ClaimData:
    """Parsed bounty claim from a GitHub comment."""
    username: str
    wallet: Optional[str] = None
    claimed_stars: int = 0
    claimed_repos: list = field(default_factory=list)
    claimed_follow: bool = False
    article_urls: list = field(default_factory=list)
    raw_text: str = ""
    comment_url: str = ""
    comment_id: int = 0
    created_at: str = ""

    @property
    def is_valid_claim(self) -> bool:
        """Check if this looks like a real claim with minimum required data."""
        return bool(self.wallet or self.claimed_stars > 0 or self.claimed_follow)


def parse_wallet(text: str) -> Optional[str]:
    """Extract RTC wallet address from comment text.

    Supports formats:
    - Wallet: my-wallet-name
    - **Wallet:** my-wallet-name
    - RTC wallet: name
    - miner_id: name
    """
    patterns = [
        r'(?:[*_]{0,2}wallet[*_:\s]{0,3}|miner[_ ]?id)[*_\s]*[:\uff1a][*_\s]*([a-zA-Z0-9_\-\.]+)',
        r'(?:RTC|rtc)[\s_-]*wallet[*_:\s]{0,3}[:\uff1a][*_\s]*([a-zA-Z0-9_\-\.]+)',
        r'(?:钱包|wallet)[*_:\s]{0,3}[:\uff1a][*_\s]*([a-zA-Z0-9_\-\.]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def parse_star_count(text: str) -> tuple[int, list[str]]:
    """Extract claimed star count and list of starred repos.

    Supports formats:
    - Stars: 45
    - Starred 30 repos
    - I starred: repo1, repo2, repo3
    """
    count = 0
    repos = []

    # Match numeric star claim
    # Handles: Stars: 45, **Stars:** 45, _Stars_: 45, Starred 45 repos
    count_match = re.search(r'(?:[*_]{0,2}stars?[*_:\s]{0,3}|starred)\s*[:\uff1a]?\s*(\d+)', text, re.IGNORECASE)
    if count_match:
        count = int(count_match.group(1))

    # Match repo URLs or names
    repo_pattern = r'(?:github\.com/)?(?:Scottcjn|scottcjn)/([a-zA-Z0-9_\-]+)'
    found_repos = re.findall(repo_pattern, text)
    if found_repos:
        repos = list(set(r.lower() for r in found_repos))
        if count == 0:
            count = len(repos)

    # Also count bare links like https://github.com/Scottcjn/REPO
    url_pattern = r'https?://github\.com/Scottcjn/([a-zA-Z0-9_\-]+)'
    url_repos = re.findall(url_pattern, text)
    if url_repos:
        repos = list(set(repos + [r.lower() for r in url_repos]))
        if count == 0:
            count = len(repos)

    return count, repos


def parse_follow(text: str) -> bool:
    """Check if claimant says they followed @Scottcjn."""
    patterns = [
        r'follow(?:ed|s)?\s+(?:@)?scottcjn',
        r'following\s+(?:@)?scottcjn',
        r'(?:[*_]{0,2}follow[*_]{0,2})\s*[:\uff1a]\s*(?:yes|✅|true|done)',
    ]
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def parse_article_urls(text: str) -> list[str]:
    """Extract article/URL proofs from comment."""
    # Match dev.to, medium.com, and generic http links
    patterns = [
        r'https?://dev\.to/[^\s\)>]+',
        r'https?://(?:www\.)?medium\.com/[^\s\)>]+',
        r'https?://[^\s\)>]+\.(?:md|html)(?:\?[^\s\)>]*)?',
    ]
    urls = []
    for pattern in patterns:
        urls.extend(re.findall(pattern, text))
    return list(set(urls))


def parse_claim_comment(comment_body: str, username: str,
                        comment_id: int = 0, created_at: str = "",
                        comment_url: str = "") -> ClaimData:
    """Main parser: extract all claim fields from a comment.

    Args:
        comment_body: The raw comment text
        username: GitHub username of the commenter
        comment_id: GitHub comment ID
        created_at: ISO timestamp of comment creation
        comment_url: Direct link to the comment

    Returns:
        ClaimData with all parsed fields
    """
    text = comment_body.strip()
    wallet = parse_wallet(text)
    claimed_stars, claimed_repos = parse_star_count(text)
    claimed_follow = parse_follow(text)
    article_urls = parse_article_urls(text)

    return ClaimData(
        username=username,
        wallet=wallet,
        claimed_stars=claimed_stars,
        claimed_repos=claimed_repos,
        claimed_follow=claimed_follow,
        article_urls=article_urls,
        raw_text=text,
        comment_url=comment_url,
        comment_id=comment_id,
        created_at=created_at,
    )
