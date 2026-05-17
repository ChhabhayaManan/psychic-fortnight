"""GitHub API client with rate limiting."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from github import Github, GithubException, Issue, PullRequest, Repository

from app.utils.logging import get_logger
from app.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


class GitHubClient:
    """
    GitHub API client with rate limiting.

    Wraps PyGithub library with async support and rate limiting
    to prevent API quota violations.
    """

    def __init__(self, token: str, rate_limiter: RateLimiter, verify_ssl: bool = True):
        """
        Initialize GitHub client.

        Args:
            token: GitHub OAuth token (Personal Access Token)
            rate_limiter: Rate limiter instance
            verify_ssl: Whether to verify SSL certificates
        """
        # Initialize with retry and timeout for robustness
        from github import Auth
        auth = Auth.Token(token)
        self.github = Github(
            auth=auth,
            verify=verify_ssl,
            timeout=30,
            retry=5,
            per_page=100  # Increase per_page for efficient listing
        )
        self.rate_limiter = rate_limiter
        self.verify_ssl = verify_ssl

        logger.info("GitHub client initialized", verify_ssl=verify_ssl, per_page=100)

    async def get_repository(self, owner: str, repo: str) -> Repository:
        """
        Get repository object.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Repository object
        """
        await self.rate_limiter.acquire()

        try:
            repository = await asyncio.to_thread(
                self.github.get_repo,
                f"{owner}/{repo}"
            )

            logger.info(
                "Repository retrieved",
                owner=owner,
                repo=repo,
                full_name=repository.full_name
            )

            return repository

        except GithubException as e:
            logger.error(
                "Failed to get repository",
                owner=owner,
                repo=repo,
                error=str(e)
            )
            raise

    async def list_pull_requests(
        self,
        repo: Repository,
        state: str = "all",
        limit: int = None
    ) -> List[PullRequest]:
        """
        List all PRs in repository.

        Args:
            repo: Repository object
            state: PR state ("open", "closed", "all")
            limit: Maximum number of PRs to fetch (None = fetch all)

        Returns:
            List of PullRequest objects
        """
        await self.rate_limiter.acquire()

        try:
            def _fetch():
                paginated = repo.get_pulls(state=state)
                
                # Use totalCount for early feedback if supported
                try:
                    total = paginated.totalCount
                    if total > 0:
                        logger.info(f"Listing {total} PRs for {repo.full_name}...")
                    else:
                        total = None
                except Exception:
                    total = None
                
                if limit:
                    from itertools import islice
                    return list(islice(paginated, limit))
                
                # Fetch all with progress logging
                results = []
                for i, pr in enumerate(paginated):
                    results.append(pr)
                    if (i + 1) % 100 == 0:
                        progress = f"{i + 1}/{total}" if total else f"{i + 1}"
                        logger.info(f"Fetched {progress} PRs")
                
                return results

            prs = await asyncio.to_thread(_fetch)

            logger.info(
                f"PRs listed -- {len(prs)}",
                count=len(prs)
            )

            return prs

        except GithubException as e:
            logger.error(
                "Failed to list PRs",
                repo=repo.full_name,
                error=str(e)
            )
            raise

    async def list_issues(
        self,
        repo: Repository,
        state: str = "all",
        limit: int = None
    ) -> List[Issue]:
        """
        List all issues in repository (excluding PRs).

        Args:
            repo: Repository object
            state: Issue state ("open", "closed", "all")
            limit: Maximum number of issues to fetch (None = fetch all)

        Returns:
            List of Issue objects (PRs are filtered out)
        """
        await self.rate_limiter.acquire()

        try:
            def _fetch_issues():
                paginated = repo.get_issues(state=state)
                
                try:
                    total = paginated.totalCount
                    if total > 0:
                        logger.info(f"Listing {total} potential items (issues+PRs) for {repo.full_name}...")
                    else:
                        total = None
                except Exception:
                    total = None

                if limit:
                    from itertools import islice
                    # Still need to filter PRs if limited, but we'll fetch 'limit' items first
                    all_items = list(islice(paginated, limit))
                    return [item for item in all_items if not item.pull_request]
                
                # Fetch all and filter PRs in one pass to avoid double iteration
                results = []
                for i, item in enumerate(paginated):
                    # Only keep issues that are NOT pull requests
                    # Accessing .pull_request here is generally safe and doesn't trigger 
                    # a full API call if the item was fetched via get_issues()
                    if not item.pull_request:
                        results.append(item)
                    
                    if (i + 1) % 100 == 0:
                        progress = f"{i + 1}/{total}" if total else f"{i + 1}"
                        logger.info(f"Fetched {progress} items (issues+PRs)")
                
                return results

            # Get issues (already filtered in the thread)
            issues = await asyncio.to_thread(_fetch_issues)

            logger.info(
                f"Issues listed -- {len(issues)}",
                count=len(issues)
            )

            return issues

        except GithubException as e:
            logger.error(
                "Failed to list issues",
                repo=repo.full_name,
                error=str(e)
            )
            raise

    async def get_pr_details(
        self,
        pr: PullRequest
    ) -> Dict[str, Any]:
        """
        Get complete PR data including comments, reviews, commits.

        Args:
            pr: PullRequest object

        Returns:
            Dictionary with complete PR data
        """
        await self.rate_limiter.acquire()

        try:
            # Fetch comments
            comments = await asyncio.to_thread(lambda: list(pr.get_comments()))

            # Fetch reviews
            reviews = await asyncio.to_thread(lambda: list(pr.get_reviews()))

            # Fetch commits
            commits = await asyncio.to_thread(lambda: list(pr.get_commits()))

            # Build complete data structure
            data = {
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
                    "assignees": [assignee.login for assignee in pr.assignees]
                },
                "description": pr.body or "",
                "comments": [
                    {
                        "id": str(comment.id),
                        "author": comment.user.login if comment.user else None,
                        "created_at": comment.created_at.isoformat() if comment.created_at else None,
                        "body": comment.body or ""
                    }
                    for comment in comments
                ],
                "reviews": [
                    {
                        "id": str(review.id),
                        "author": review.user.login if review.user else None,
                        "state": review.state,
                        "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None,
                        "body": review.body or ""
                    }
                    for review in reviews
                ],
                "commits": [
                    {
                        "sha": commit.sha,
                        "message": commit.commit.message,
                        "author": commit.commit.author.name if commit.commit.author else None,
                        "date": commit.commit.author.date.isoformat() if commit.commit.author and commit.commit.author.date else None
                    }
                    for commit in commits
                ],
                "files_changed": pr.changed_files,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "merged": pr.merged,
                "mergeable": pr.mergeable,
                "ingested_at": datetime.now().isoformat()
            }

            logger.info(
                "PR details fetched",
                pr_number=pr.number,
                comments=len(comments),
                reviews=len(reviews),
                commits=len(commits)
            )

            return data

        except GithubException as e:
            logger.error(
                "Failed to get PR details",
                pr_number=pr.number,
                error=str(e)
            )
            raise

    async def get_issue_details(
        self,
        issue: Issue
    ) -> Dict[str, Any]:
        """
        Get complete issue data including comments.

        Args:
            issue: Issue object

        Returns:
            Dictionary with complete issue data
        """
        await self.rate_limiter.acquire()

        try:
            # Fetch comments
            comments = await asyncio.to_thread(lambda: list(issue.get_comments()))

            # Build complete data structure
            data = {
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
                    "assignees": [assignee.login for assignee in issue.assignees]
                },
                "description": issue.body or "",
                "comments": [
                    {
                        "id": str(comment.id),
                        "author": comment.user.login if comment.user else None,
                        "created_at": comment.created_at.isoformat() if comment.created_at else None,
                        "body": comment.body or ""
                    }
                    for comment in comments
                ],
                "ingested_at": datetime.now().isoformat()
            }

            logger.info(
                "Issue details fetched",
                issue_number=issue.number,
                comments=len(comments)
            )

            return data

        except GithubException as e:
            logger.error(
                "Failed to get issue details",
                issue_number=issue.number,
                error=str(e)
            )
            raise

    def close(self):
        """Close GitHub connection."""
        if hasattr(self.github, 'close'):
            self.github.close()
        logger.info("GitHub client closed")

# Made with Bob
