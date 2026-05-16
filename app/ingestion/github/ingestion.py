"""GitHub repository ingestion implementation."""

from datetime import datetime
from typing import Any, Dict

from app.ingestion.base import BaseIngestion
from app.ingestion.github.client import GitHubClient
from app.memory.raw_storage import RawDataStorage
from app.models.ingestion import DiscoveryResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GitHubIngestion(BaseIngestion):
    """
    GitHub repository ingestion.

    Discovers and fetches all PRs and Issues from a GitHub repository
    using OAuth token authentication.
    """

    def __init__(
        self,
        owner: str,
        repo: str,
        client: GitHubClient,
        storage: RawDataStorage
    ):
        """
        Initialize GitHub ingestion.

        Args:
            owner: Repository owner
            repo: Repository name
            client: GitHubClient instance
            storage: RawDataStorage instance
        """
        self.owner = owner
        self.repo = repo
        self.client = client
        self.storage = storage
        self._repository = None

        logger.info(
            "GitHub ingestion initialized",
            owner=owner,
            repo=repo
        )

    def get_source_id(self) -> str:
        """
        Get unique identifier for this source.

        Returns:
            Source identifier in format "owner_repo"
        """
        return f"{self.owner}_{self.repo}"

    async def validate(self) -> bool:
        """
        Validate GitHub connection.

        Returns:
            True if connection is valid, False otherwise
        """
        try:
            self._repository = await self.client.get_repository(
                self.owner,
                self.repo
            )

            logger.info(
                "GitHub connection validated",
                owner=self.owner,
                repo=self.repo,
                full_name=self._repository.full_name
            )

            return True

        except Exception as e:
            logger.error(
                "GitHub connection validation failed",
                owner=self.owner,
                repo=self.repo,
                error=str(e)
            )
            return False

    async def discover(self) -> DiscoveryResult:
        """
        Discover all PRs and Issues.

        Returns:
            DiscoveryResult with PR and Issue numbers
        """
        # Ensure repository is loaded
        if not self._repository:
            self._repository = await self.client.get_repository(
                self.owner,
                self.repo
            )

        logger.info(
            "Starting discovery",
            source_id=self.get_source_id()
        )

        # Discover PRs
        prs = await self.client.list_pull_requests(
            self._repository,
            state="all"
        )
        pr_numbers = [pr.number for pr in prs]

        # Discover Issues (excluding PRs)
        issues = await self.client.list_issues(
            self._repository,
            state="all"
        )
        issue_numbers = [issue.number for issue in issues]

        # Create discovery result
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

    async def fetch(self, item_id: str) -> Dict[str, Any]:
        """
        Fetch raw data for a single item.

        Args:
            item_id: Item identifier in format "source_id_type_number"

        Returns:
            Dictionary containing raw item data
        """
        # Parse item_id
        parts = item_id.split('_')
        if len(parts) < 4:
            raise ValueError(f"Invalid item_id format: {item_id}")

        item_type = parts[-2]  # "pr" or "issue"
        item_number = int(parts[-1])

        if item_type == "pr":
            return await self.fetch_pr(item_number)
        elif item_type == "issue":
            return await self.fetch_issue(item_number)
        else:
            raise ValueError(f"Unknown item type: {item_type}")

    async def fetch_pr(self, pr_number: int) -> Dict[str, Any]:
        """
        Fetch complete PR data.

        Args:
            pr_number: PR number

        Returns:
            Dictionary with complete PR data
        """
        # Ensure repository is loaded
        if not self._repository:
            self._repository = await self.client.get_repository(
                self.owner,
                self.repo
            )

        logger.info(
            "Fetching PR",
            source_id=self.get_source_id(),
            pr_number=pr_number
        )

        # Get PR object
        pr = self._repository.get_pull(pr_number)

        # Fetch complete details
        data = await self.client.get_pr_details(pr)

        logger.info(
            "PR fetched",
            source_id=self.get_source_id(),
            pr_number=pr_number
        )

        return data

    async def fetch_issue(self, issue_number: int) -> Dict[str, Any]:
        """
        Fetch complete issue data.

        Args:
            issue_number: Issue number

        Returns:
            Dictionary with complete issue data
        """
        # Ensure repository is loaded
        if not self._repository:
            self._repository = await self.client.get_repository(
                self.owner,
                self.repo
            )

        logger.info(
            "Fetching issue",
            source_id=self.get_source_id(),
            issue_number=issue_number
        )

        # Get issue object
        issue = self._repository.get_issue(issue_number)

        # Fetch complete details
        data = await self.client.get_issue_details(issue)

        logger.info(
            "Issue fetched",
            source_id=self.get_source_id(),
            issue_number=issue_number
        )

        return data

# Made with Bob
