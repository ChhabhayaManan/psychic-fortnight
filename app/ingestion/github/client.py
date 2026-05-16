"""GitHub API client with rate limiting."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List

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

    def __init__(self, token: str, rate_limiter: RateLimiter):
        """
        Initialize GitHub client.

        Args:
            token: GitHub OAuth token (Personal Access Token)
            rate_limiter: Rate limiter instance
        """
        self.github = Github(token)
        self.rate_limiter = rate_limiter

        logger.info("GitHub client initialized")

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
        state: str = "all"
    ) -> List[PullRequest]:
        """
        List all PRs in repository.

        Args:
            repo: Repository object
            state: PR state ("open", "closed", "all")

        Returns:
            List of PullRequest objects
        """
        await self.rate_limiter.acquire()

        try:
            prs = await asyncio.to_thread(
                lambda: list(repo.get_pulls(state=state))
            )

            logger.info(
                "PRs listed",
                repo=repo.full_name,
                state=state,
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
        state: str = "all"
    ) -> List[Issue]:
        """
        List all issues in repository (excluding PRs).

        Args:
            repo: Repository object
            state: Issue state ("open", "closed", "all")

        Returns:
            List of Issue objects (PRs are filtered out)
        """
        await self.rate_limiter.acquire()

        try:
            # Get all issues (includes PRs)
            all_issues = await asyncio.to_thread(
                lambda: list(repo.get_issues(state=state))
            )

            # Filter out PRs (issues with pull_request attribute)
            issues = [issue for issue in all_issues if not issue.pull_request]

            logger.info(
                "Issues listed",
                repo=repo.full_name,
                state=state,
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
