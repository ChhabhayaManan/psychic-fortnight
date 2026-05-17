import re
import os

filepath = 'app/ingestion/github/client.py'
if os.path.exists(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add limit to list_pull_requests
    old_pr_def = r'''    async def list_pull_requests\(
        self,
        repo: Repository,
        state: str = "all"
    \) -> List\[PullRequest\]:'''
    
    new_pr_def = '''    async def list_pull_requests(
        self,
        repo: Repository,
        state: str = "all",
        limit: int = 50
    ) -> List[PullRequest]:'''
    content = re.sub(old_pr_def, new_pr_def, content)

    old_pr_fetch = r'''            prs = await asyncio\.to_thread\(
                lambda: list\(repo\.get_pulls\(state=state\)\)
            \)'''
    new_pr_fetch = '''            prs = await asyncio.to_thread(
                lambda: list(repo.get_pulls(state=state)[:limit]) if limit else list(repo.get_pulls(state=state))
            )'''
    content = re.sub(old_pr_fetch, new_pr_fetch, content)

    # Add limit to list_issues
    old_issue_def = r'''    async def list_issues\(
        self,
        repo: Repository,
        state: str = "all"
    \) -> List\[Issue\]:'''
    new_issue_def = '''    async def list_issues(
        self,
        repo: Repository,
        state: str = "all",
        limit: int = 50
    ) -> List[Issue]:'''
    content = re.sub(old_issue_def, new_issue_def, content)

    old_issue_fetch = r'''            # Get all issues \(includes PRs\)
            all_issues = await asyncio\.to_thread\(
                lambda: list\(repo\.get_issues\(state=state\)\)
            \)'''
    new_issue_fetch = '''            # Get all issues (includes PRs)
            all_issues = await asyncio.to_thread(
                lambda: list(repo.get_issues(state=state)[:limit]) if limit else list(repo.get_issues(state=state))
            )'''
    content = re.sub(old_issue_fetch, new_issue_fetch, content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

filepath = 'app/ingestion/github/ingestion.py'
if os.path.exists(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    old_discover = r'''        # Discover PRs
        prs = await self\.client\.list_pull_requests\(
            self\._repository,
            state="all"
        \)
        pr_numbers = \[pr\.number for pr in prs\]

        # Discover Issues \(excluding PRs\)
        issues = await self\.client\.list_issues\(
            self\._repository,
            state="all"
        \)'''
    
    new_discover = '''        # Discover PRs
        prs = await self.client.list_pull_requests(
            self._repository,
            state="all",
            limit=50
        )
        pr_numbers = [pr.number for pr in prs]

        # Discover Issues (excluding PRs)
        issues = await self.client.list_issues(
            self._repository,
            state="all",
            limit=50
        )'''
    content = re.sub(old_discover, new_discover, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

# Modify workflow.py to save state initially
filepath = 'app/ingestion/github/workflow.py'
if os.path.exists(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    old_run = r'''    async def run\(self\) -> IngestionSourceState:
        """
        Run the complete ingestion workflow.

        Returns:
            Final ingestion state
        """
        logger\.info\("Starting ingestion workflow", source_id=self\.source_id\)

        # Step 1: Validate repository access'''
    
    new_run = '''    async def run(self) -> IngestionSourceState:
        """
        Run the complete ingestion workflow.

        Returns:
            Final ingestion state
        """
        logger.info("Starting ingestion workflow", source_id=self.source_id)
        
        # Save initial state immediately so UI doesn't think it failed to start
        from datetime import datetime
        existing_state = self.state_manager.load_state(self.source_id)
        if not existing_state:
            initial_state = IngestionSourceState(
                source_id=self.source_id,
                repository=f"{self.owner}/{self.repo}",
                discovered_at=datetime.now().isoformat(),
                pr_count=0,
                issue_count=0,
                total_count=0
            )
            self.state_manager.save_state(initial_state)

        # Step 1: Validate repository access'''
    content = re.sub(old_run, new_run, content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Patch limits and initial state executed.")
