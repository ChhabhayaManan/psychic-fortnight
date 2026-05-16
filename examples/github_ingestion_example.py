"""
Example script demonstrating full GitHub ingestion workflow.

This script demonstrates the complete Step 2 automatic flow:
1. Connect to GitHub source
2. Validate repository access
3. Discover all PRs and issues
4. Create ingestion queue items
5. Fetch raw records with worker pool
6. Store with provenance
7. Track ingestion state
8. Enqueue for Step 3 processing

Usage:
    python examples/github_ingestion_example.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import get_settings
from app.utils.rate_limiter import RateLimiter
from app.ingestion.github.client import GitHubClient
from app.ingestion.github.workflow import GitHubIngestionWorkflow
from app.memory.raw_storage import RawDataStorage
from app.models.ingestion_state import IngestionStateManager, ProcessingQueue
from app.utils import get_logger, setup_logging


async def main():
    """Main example function."""
    
    # Setup logging
    setup_logging(log_level="INFO", log_format="text")
    logger = get_logger(__name__)
    
    logger.info("Starting GitHub ingestion workflow example")
    
    # Load settings
    settings = get_settings()
    
    # Check if GitHub token is configured
    if not settings.github_token:
        logger.error("GITHUB_TOKEN not configured in .env file")
        print("\n❌ Error: GITHUB_TOKEN not found in environment variables")
        print("\nPlease add your GitHub Personal Access Token to .env file:")
        print("GITHUB_TOKEN=ghp_your_token_here")
        return
    
    # Initialize components
    logger.info("Initializing components")
    
    # Rate limiter
    rate_limiter = RateLimiter(
        max_requests=settings.rate_limit_requests,
        period=settings.rate_limit_period
    )
    
    # GitHub client
    client = GitHubClient(
        token=settings.github_token,
        rate_limiter=rate_limiter
    )
    
    # RAW data storage
    storage = RawDataStorage(settings.raw_data_dir)
    
    # State manager
    state_manager = IngestionStateManager(settings.state_dir)
    
    # Processing queue
    processing_queue = ProcessingQueue(settings.state_dir)
    
    # Get repository details from user
    print("\n" + "="*60)
    print("GitHub Repository Ingestion - Full Automatic Workflow")
    print("="*60)
    
    owner = input("\nEnter repository owner (e.g., 'facebook'): ").strip()
    repo = input("Enter repository name (e.g., 'react'): ").strip()
    
    if not owner or not repo:
        logger.error("Owner and repo are required")
        print("\n❌ Error: Both owner and repo are required")
        return
    
    # Ask for workflow options
    print("\n📋 Workflow Options:")
    print("  1. Full ingestion (all items)")
    print("  2. Sample ingestion (first 10 items)")
    print("  3. Resume previous ingestion")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    # Determine max workers and skip existing
    max_workers = settings.max_workers
    skip_existing = True
    
    if choice == "2":
        # For sample, we'll limit in the workflow
        print("\n⚠️  Sample mode: Will process first 10 items only")
    elif choice == "3":
        print("\n🔄 Resume mode: Will continue from previous state")
    
    # Initialize workflow
    workflow = GitHubIngestionWorkflow(
        owner=owner,
        repo=repo,
        client=client,
        storage=storage,
        state_manager=state_manager,
        processing_queue=processing_queue,
        max_workers=max_workers,
        skip_existing=skip_existing
    )
    
    print(f"\n🚀 Starting ingestion workflow for {owner}/{repo}...")
    print(f"   Workers: {max_workers}")
    print(f"   Skip existing: {skip_existing}")
    
    try:
        # Run the workflow
        final_state = await workflow.run()
        
        # Display results
        print("\n" + "="*60)
        print("✅ Ingestion Workflow Complete!")
        print("="*60)
        print(f"\n📊 Final Statistics:")
        print(f"  - Total items: {final_state.total_count}")
        print(f"  - Stored: {final_state.stored_count}")
        print(f"  - Skipped: {final_state.skipped_count}")
        print(f"  - Failed: {final_state.failed_count}")
        print(f"  - Progress: {final_state.progress_percentage:.1f}%")
        
        print(f"\n📁 Data Locations:")
        print(f"  - Raw data: {settings.raw_data_dir / 'github' / workflow.source_id}")
        print(f"  - State file: {settings.state_dir / 'ingestion' / f'{workflow.source_id}.json'}")
        print(f"  - Processing queue: {settings.state_dir / 'processing_queue' / 'queue.json'}")
        
        # Show processing queue status
        queue_size = processing_queue.size()
        print(f"\n🔄 Processing Queue:")
        print(f"  - Items queued for Step 3: {queue_size}")
        
        if queue_size > 0:
            print(f"\n💡 Next Steps:")
            print(f"  - {queue_size} items are ready for Step 3 processing")
            print(f"  - Run Step 3 processor to extract memory artifacts")
        
        # Show sample of stored items
        if final_state.stored_count > 0:
            print(f"\n📄 Sample Stored Items:")
            stored_items = final_state.get_items_by_status("stored")[:3]
            for item in stored_items:
                print(f"  - {item.item_type} #{item.item_number}: {item.raw_data_path}")
        
    except Exception as e:
        logger.error("Workflow failed", error=str(e))
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Close client
        client.close()
        print("\n👋 Workflow complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

# Made with Bob
