"""
Report Generator — Formats verification results as a GitHub comment.
"""

from checkers import VerificationReport, CheckResult


def generate_report(report: VerificationReport) -> str:
    """Generate a formatted Markdown report for GitHub comment.

    Args:
        report: Complete verification report

    Returns:
        Markdown string ready to post as a comment
    """
    lines = []

    # Header
    lines.append(f"## 🤖 Automated Verification for @{report.username}")
    lines.append("")

    # Status badge
    if report.all_passed:
        lines.append("> **Status: ✅ ALL CHECKS PASSED**")
    elif report.pass_count >= 3:
        lines.append("> **Status: ⚠️ PARTIALLY VERIFIED**")
    else:
        lines.append("> **Status: ❌ VERIFICATION FAILED**")
    lines.append("")

    # Check results table
    lines.append("| Check | Result |")
    lines.append("|-------|--------|")

    for check in report.checks:
        icon = "✅" if check.passed else "❌"
        # Take first line of details for table
        first_line = check.details.split("\n")[0]
        lines.append(f"| {check.name} | {icon} {first_line} |")

    lines.append("")

    # Detailed results
    lines.append("### Detailed Results")
    lines.append("")

    for check in report.checks:
        lines.append(f"**{check.name}**")
        for detail in check.details.split("\n"):
            if detail.strip():
                lines.append(f"- {detail.strip()}")
        lines.append("")

    # Payout suggestion
    if report.suggested_payout > 0:
        lines.append("### 💰 Suggested Payout")
        lines.append(f"**{report.suggested_payout} RTC**")
        lines.append("")

    # Warnings
    if report.warnings:
        lines.append("### ⚠️ Warnings")
        for w in report.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("*Automated by [Bounty Verifier](https://github.com/wuxiaobinsh-gif/bounty-verifier) — "
                 "human approval required for payment*")
    lines.append("")

    return "\n".join(lines)


def generate_summary_stats(report: VerificationReport) -> dict:
    """Generate summary stats for logging/webhook."""
    return {
        "username": report.username,
        "wallet": report.wallet,
        "passed": report.pass_count,
        "total_checks": len(report.checks),
        "all_passed": report.all_passed,
        "suggested_payout": report.suggested_payout,
        "warnings_count": len(report.warnings),
    }
