"""GitHub client — fast discovery + detailed fetch."""

import asyncio
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from github import Github, GithubException
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository

from app.utils.logging import get_logger
from app.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


class GitHubClient:
    """
    GitHub API client.

    Two distinct operations:
      - list_pr_numbers / list_issue_numbers  → fast; returns only (number, title) tuples
      - get_pr_details / get_issue_details    → slow; fetches comments, reviews, commits
    """

    def __init__(
        self,
        token: str,
        rate_limiter: RateLimiter,
        per_page: int = 100,
        verify_ssl: bool = True
    ):
        self.github = Github(login_or_token=token, per_page=per_page, verify=verify_ssl)
        self.rate_limiter = rate_limiter
        self.per_page = per_page

        logger.info(
            "GitHub client initialized",
            verify_ssl=verify_ssl,
            per_page=per_page
        )

    # ─── Repository ──────────────────────────────────────────────────────────

    async def get_repository(self, owner: str, repo: str) -> Repository:
        await self.rate_limiter.acquire()
        repo_obj = await asyncio.to_thread(self.github.get_repo, f"{owner}/{repo}")
        logger.info("Repository retrieved", owner=owner, repo=repo, full_name=repo_obj.full_name)
        return repo_obj

    # ─── Streaming page-based discovery ──────────────────────────────────────

    async def stream_pr_pages(
        self,
        repo: Repository,
        state: str = "all",
    ):
        """
        Async generator yielding one page of PR numbers at a time.
        Each page = one GitHub API call = up to 100 PR numbers.
        Yields: List[int]
        """
        await self.rate_limiter.acquire()

        def _get_total_and_first_page():
            paginated = repo.get_pulls(state=state)
            total = None
            try:
                total = paginated.totalCount
            except Exception:
                pass
            page0 = paginated.get_page(0)
            return total, paginated, page0

        total, paginated, page0 = await asyncio.to_thread(_get_total_and_first_page)
        total_pages = ((total or 0) + 99) // 100

        if total:
            logger.info(f"PR stream: {total} total PRs across ~{total_pages} pages")
            print(f"[INGEST] {total} PRs to process (~{total_pages} pages of 100)")

        if not page0:
            return

        yield [pr.number for pr in page0]

        for page_num in range(1, total_pages + 1):
            await self.rate_limiter.acquire()

            def _fetch_page(n=page_num):
                return paginated.get_page(n)

            items = await asyncio.to_thread(_fetch_page)
            if not items:
                break
            yield [pr.number for pr in items]

    async def stream_issue_pages(
        self,
        repo: Repository,
        state: str = "all",
    ):
        """
        Async generator yielding one page of ISSUE numbers at a time (PRs filtered out).
        Each page = one GitHub API call, returns up to 100 real issues.
        Yields: List[int]
        """
        await self.rate_limiter.acquire()

        def _get_total_and_first_page():
            paginated = repo.get_issues(state=state)
            total = None
            try:
                total = paginated.totalCount
            except Exception:
                pass
            page0 = paginated.get_page(0)
            return total, paginated, page0

        total, paginated, page0 = await asyncio.to_thread(_get_total_and_first_page)
        total_pages = ((total or 0) + 99) // 100

        if total:
            logger.info(f"Issue stream: ~{total} items (issues+PRs) across ~{total_pages} pages")
            print(f"[INGEST] ~{total} issues+PRs to scan for real issues (~{total_pages} pages)")

        if page0 is not None:
            filtered = [i.number for i in page0 if i.pull_request is None]
            if filtered:
                yield filtered

        for page_num in range(1, total_pages + 1):
            await self.rate_limiter.acquire()

            def _fetch_page(n=page_num):
                return paginated.get_page(n)

            items = await asyncio.to_thread(_fetch_page)
            if not items:
                break
            filtered = [i.number for i in items if i.pull_request is None]
            if filtered:
                yield filtered

    # ─── Detailed fetch (one item at a time, after discovery) ────────────────

    async def get_pr_details(self, repo: Repository, pr_number: int) -> Dict[str, Any]:
        """Fetch full PR data including comments, reviews, commits."""
        await self.rate_limiter.acquire()

        def _fetch():
            pr = repo.get_pull(pr_number)
            comments = list(pr.get_comments())
            reviews = list(pr.get_reviews())
            commits = list(pr.get_commits())
            return pr, comments, reviews, commits

        try:
            pr, comments, reviews, commits = await asyncio.to_thread(_fetch)

            return {
                "source": {
                    "type": "github",
                    "repository": pr.base.repo.full_name,
                    "pr_number": pr.number,
                    "url": pr.html_url
                },
                "metadata": {
                    "title": pr.title,
                    "state": pr.state,
                    "created_at": pr.created_at.isoformat() if pr.created_at else None,
                    "updated_at": pr.updated_at.isoformat() if pr.updated_at else None,
                    "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
                    "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                    "author": pr.user.login if pr.user else None,
                    "labels": [label.name for label in pr.labels],
                    "milestone": pr.milestone.title if pr.milestone else None,
                    "assignees": [a.login for a in pr.assignees]
                },
                "description": pr.body or "",
                "comments": [
                    {
                        "id": str(c.id),
                        "author": c.user.login if c.user else None,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                        "body": c.body or ""
                    }
                    for c in comments
                ],
                "reviews": [
                    {
                        "id": str(r.id),
                        "author": r.user.login if r.user else None,
                        "state": r.state,
                        "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                        "body": r.body or ""
                    }
                    for r in reviews
                ],
                "commits": [
                    {
                        "sha": c.sha,
                        "message": c.commit.message,
                        "author": c.commit.author.name if c.commit.author else None,
                        "date": c.commit.author.date.isoformat() if c.commit.author and c.commit.author.date else None
                    }
                    for c in commits
                ],
                "files_changed": pr.changed_files,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "merged": pr.merged,
                "mergeable": pr.mergeable,
                "ingested_at": datetime.now().isoformat()
            }
        except GithubException as e:
            logger.error("Failed to get PR details", pr_number=pr_number, error=str(e))
            raise

    async def get_issue_details(self, repo: Repository, issue_number: int) -> Dict[str, Any]:
        """Fetch full issue data including comments."""
        await self.rate_limiter.acquire()

        def _fetch():
            issue = repo.get_issue(issue_number)
            comments = list(issue.get_comments())
            return issue, comments

        try:
            issue, comments = await asyncio.to_thread(_fetch)

            return {
                "source": {
                    "type": "github",
                    "repository": issue.repository.full_name,
                    "issue_number": issue.number,
                    "url": issue.html_url
                },
                "metadata": {
                    "title": issue.title,
                    "state": issue.state,
                    "created_at": issue.created_at.isoformat() if issue.created_at else None,
                    "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
                    "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                    "author": issue.user.login if issue.user else None,
                    "labels": [label.name for label in issue.labels],
                    "milestone": issue.milestone.title if issue.milestone else None,
                    "assignees": [a.login for a in issue.assignees]
                },
                "description": issue.body or "",
                "comments": [
                    {
                        "id": str(c.id),
                        "author": c.user.login if c.user else None,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                        "body": c.body or ""
                    }
                    for c in comments
                ],
                "ingested_at": datetime.now().isoformat()
            }
        except GithubException as e:
            logger.error("Failed to get issue details", issue_number=issue_number, error=str(e))
            raise

    def close(self):
        if hasattr(self.github, 'close'):
            self.github.close()
        logger.info("GitHub client closed")
