---
name: Bounty Claim Verifier
description: GitHub Action that auto-verifies bounty claim comments on rustchain-bounties issues
version: 1.0.0
author: wuxiaobinsh-gif
---

# Bounty Claim Verifier

A GitHub Action bot that automatically verifies bounty claim comments on GitHub issues — checking star counts, follow status, wallet balances, article URLs, and duplicate claims. Eliminates hours of manual verification.

## Features

1. **Star/Follow Verification** — Checks if claimant stars target repos and follows the owner
2. **Wallet Existence Check** — Queries RustChain node API for wallet balance
3. **Article/URL Verification** — Validates dev.to/Medium links are live with word count
4. **Duplicate Claim Detection** — Scans previous comments for prior payouts
5. **Auto-Generated Report** — Posts a formatted verification summary comment

## Installation

1. Copy `action-workflow.yml` to `.github/workflows/verify-claim.yml` in your repo
2. Set repository secrets:
   - `GITHUB_TOKEN` (auto-provided by GitHub)
   - `RUSTCHAIN_NODE_URL` (default: `https://50.28.86.131`)
3. Add `config/bounty-rules.yml` for customizable rules
4. Done! Bot auto-triggers on new issue comments

## How It Works

```
[New Comment] → [Keyword Detection] → [Parse Claim] → [Run Checks] → [Post Report]
```

Trigger keywords: "Claiming", "Wallet:", "Stars:", "GitHub:"

## Configuration

Edit `config/bounty-rules.yml` to customize:
- RTC rates per star
- Follow multipliers
- Minimum thresholds
- Duplicate claim window

## File Structure

```
bounty-verifier/
├── src/
│   ├── parser.py          # Extract claim data from comments
│   ├── checkers.py         # All verification checks
│   ├── reporter.py         # Generate formatted report
│   └── main.py             # Entry point / orchestrator
├── config/
│   └── bounty-rules.yml    # Configurable rules
├── .github/workflows/
│   └── verify-claim.yml    # GitHub Action workflow
├── tests/
│   └── test_checks.py      # Unit tests
├── requirements.txt
└── README.md
```

## Milestone Rewards (per Issue #747)

| Milestone | Reward | Status |
|-----------|--------|--------|
| Star/follow verification | 30 RTC | ✅ Implemented |
| Wallet existence check | +10 RTC | ✅ Implemented |
| Article/URL verification | +10 RTC | ✅ Implemented |
| Dev.to word count + quality | +10 RTC | ✅ Implemented |
| Duplicate claim detection | +15 RTC | ✅ Implemented |

**Total: 75 RTC**
