"""
Unit tests for Bounty Verifier.

Run with: python -m pytest tests/ -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from parser import parse_claim_comment, parse_wallet, parse_star_count, parse_follow


# ============================================================
# Parser Tests
# ============================================================

class TestWalletParser:
    def test_basic_wallet(self):
        text = "Wallet: my-awesome-wallet"
        assert parse_wallet(text) == "my-awesome-wallet"

    def test_bold_wallet(self):
        text = "**Wallet:** test_wallet_123"
        assert parse_wallet(text) == "test_wallet_123"

    def test_miner_id(self):
        text = "miner_id: hp-pro-explorer"
        assert parse_wallet(text) == "hp-pro-explorer"

    def test_rtc_wallet(self):
        text = "RTC wallet: wuxiaobin2026"
        assert parse_wallet(text) == "wuxiaobin2026"

    def test_chinese_colon(self):
        text = "钱包：test_wallet"
        # Chinese colon should work too
        result = parse_wallet(text)
        assert result == "test_wallet"

    def test_no_wallet(self):
        text = "This is just a regular comment"
        assert parse_wallet(text) is None


class TestStarParser:
    def test_numeric_stars(self):
        count, repos = parse_star_count("Stars: 45")
        assert count == 45

    def test_repos_from_urls(self):
        text = "I starred https://github.com/Scottcjn/Rustchain and https://github.com/Scottcjn/bottube"
        count, repos = parse_star_count(text)
        assert count == 2
        assert "rustchain" in repos
        assert "bottube" in repos

    def test_mixed_format(self):
        text = "Starred 30 repos including Scottcjn/Rustchain, Scottcjn/ram-coffers"
        count, repos = parse_star_count(text)
        assert count >= 2

    def test_no_stars(self):
        count, repos = parse_star_count("Just saying hi")
        assert count == 0


class TestFollowParser:
    def test_followed(self):
        assert parse_follow("I followed @Scottcjn") is True

    def test_follows(self):
        assert parse_follow("Follow: yes") is True

    def test_following(self):
        assert parse_follow("following Scottcjn") is True

    def test_no_follow(self):
        assert parse_follow("Nothing about following here") is False


class TestClaimParser:
    def test_full_claim(self):
        text = """## My Claim
**Wallet:** test-wallet-123
**Stars:** 45 repos starred
**Follow:** I followed @Scottcjn
**Article:** https://dev.to/myarticle
"""
        claim = parse_claim_comment(text, username="testuser")
        assert claim.username == "testuser"
        assert claim.wallet == "test-wallet-123"
        assert claim.claimed_stars == 45
        assert claim.claimed_follow is True
        assert len(claim.article_urls) >= 1
        assert claim.is_valid_claim

    def test_minimal_claim(self):
        text = "Wallet: minimal-wallet"
        claim = parse_claim_comment(text, username="minimal")
        assert claim.wallet == "minimal-wallet"
        assert claim.is_valid_claim

    def test_invalid_claim(self):
        text = "This is not a claim at all"
        claim = parse_claim_comment(text, username="random")
        assert not claim.is_valid_claim


# ============================================================
# Integration Tests (mocked API calls)
# ============================================================

class TestReportGeneration:
    def test_report_format(self):
        from checkers import VerificationReport, CheckResult
        from reporter import generate_report

        report = VerificationReport(username="testuser", wallet="test-wallet")
        report.add_check(CheckResult(
            name="Star & Follow",
            passed=True,
            details="✅ Follows @Scottcjn\n⭐ Stars 10 repos"
        ))
        report.add_check(CheckResult(
            name="Wallet Check",
            passed=True,
            details="✅ Wallet exists — Balance: 50 RTC"
        ))
        report.suggested_payout = 12.0

        md = generate_report(report)
        assert "testuser" in md
        assert "test-wallet" not in md or "Wallet Check" in md
        assert "12.0 RTC" in md
        assert "ALL CHECKS PASSED" in md


# Run tests
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
