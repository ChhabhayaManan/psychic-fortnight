"""GitHub ingestion — fast discovery then detail fetch."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.ingestion.base import BaseIngestion
from app.ingestion.github.client import GitHubClient
from app.memory.raw_storage import RawDataStorage
from app.models.ingestion import DiscoveryResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GitHubIngestion(BaseIngestion):
    """
    GitHub ingestion.

    Phase 1 — discover(): get PR and issue NUMBERS ONLY (cheap, fast).
    Phase 2 — fetch_pr() / fetch_issue(): get full detail for one item.
    """

    def __init__(
        self,
        owner: str,
        repo: str,
        client: GitHubClient,
        storage: RawDataStorage
    ):
        self.owner = owner
        self.repo = repo
        self.client = client
        self.storage = storage
        self._repository = None

        logger.info("GitHub ingestion initialized", owner=owner, repo=repo)

    def get_source_id(self) -> str:
        return f"{self.owner}_{self.repo}"

    async def _ensure_repo(self):
        if not self._repository:
            self._repository = await self.client.get_repository(self.owner, self.repo)

    async def validate(self) -> bool:
        try:
            await self._ensure_repo()
            logger.info(
                "GitHub connection validated",
                owner=self.owner,
                repo=self.repo,
                full_name=self._repository.full_name
            )
            return True
        except Exception as e:
            logger.error("GitHub validation failed", owner=self.owner, repo=self.repo, error=str(e))
            return False

    async def discover(
        self,
        pr_limit: Optional[int] = None,
        issue_limit: Optional[int] = None
    ) -> DiscoveryResult:
        """
        Discover PR and issue NUMBERS ONLY — no full-detail API calls.
        This is fast even for repos with thousands of PRs/issues.
        """
        await self._ensure_repo()

        logger.info(
            "Starting discovery (numbers only)",
            source_id=self.get_source_id(),
            pr_limit=pr_limit,
            issue_limit=issue_limit
        )

        # Fast: only fetches PR list, no individual PR calls
        logger.info("Discovering PR numbers...")
        pr_numbers = await self.client.list_pr_numbers(
            self._repository,
            state="all",
            limit=pr_limit
        )
        logger.info(f"Discovered {len(pr_numbers)} PR numbers")

        # Fast: list_issue_numbers uses pull_request from list payload (no extra API calls)
        logger.info("Discovering issue numbers...")
        issue_numbers = await self.client.list_issue_numbers(
            self._repository,
            state="all",
            limit=issue_limit
        )
        logger.info(f"Discovered {len(issue_numbers)} issue numbers")

        result = DiscoveryResult(
            source_id=self.get_source_id(),
            pr_numbers=pr_numbers,
            issue_numbers=issue_numbers,
            total_count=len(pr_numbers) + len(issue_numbers),
            discovered_at=datetime.now()
        )

        logger.info(
            "Discovery complete",
            source_id=self.get_source_id(),
            prs=len(pr_numbers),
            issues=len(issue_numbers),
            total=result.total_count
        )

        # Store source metadata
        metadata = {
            "owner": self.owner,
            "repo": self.repo,
            "full_name": self._repository.full_name,
            "description": self._repository.description,
            "language": self._repository.language,
            "stars": self._repository.stargazers_count,
            "forks": self._repository.forks_count,
            "discovered_at": result.discovered_at.isoformat(),
            "pr_count": len(pr_numbers),
            "issue_count": len(issue_numbers)
        }
        self.storage.store_source_metadata(self.get_source_id(), metadata)

        return result

    async def fetch_pr(self, pr_number: int) -> Dict[str, Any]:
        """Fetch full detail for a single PR."""
        await self._ensure_repo()
        logger.info(f"Fetching PR #{pr_number}", source_id=self.get_source_id())
        data = await self.client.get_pr_details(self._repository, pr_number)
        logger.info(f"PR #{pr_number} fetched", source_id=self.get_source_id())
        return data

    async def fetch_issue(self, issue_number: int) -> Dict[str, Any]:
        """Fetch full detail for a single issue."""
        await self._ensure_repo()
        logger.info(f"Fetching issue #{issue_number}", source_id=self.get_source_id())
        data = await self.client.get_issue_details(self._repository, issue_number)
        logger.info(f"Issue #{issue_number} fetched", source_id=self.get_source_id())
        return data

    async def fetch(self, item_id: str) -> Dict[str, Any]:
        """Legacy fetch by item_id string. Used by old workflow code."""
        parts = item_id.split('_')
        if len(parts) < 4:
            raise ValueError(f"Invalid item_id format: {item_id}")
        item_type = parts[-2]
        item_number = int(parts[-1])
        if item_type == "pr":
            return await self.fetch_pr(item_number)
        elif item_type == "issue":
            return await self.fetch_issue(item_number)
        else:
            raise ValueError(f"Unknown item type: {item_type}")
