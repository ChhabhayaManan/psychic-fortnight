# Additional Ingestion Fixes - Round 2

## Date: 2026-05-16

## Summary
Fixed critical issues preventing full repository ingestion and added automatic extraction functionality.

---

## Issues Fixed

### 1. Limited Item Discovery (Only 72 items instead of 2000-3000) ✅

**Problem:** Ingestion was only fetching 50 PRs + 50 issues = 100 items maximum due to hardcoded limits.

**Root Cause:** 
- `app/ingestion/github/ingestion.py` lines 114 and 122 had `limit=50` hardcoded
- This prevented discovery of all items in large repositories

**Fix:**
```python
# Before
prs = await self.client.list_pull_requests(
    self._repository,
    state="all",
    limit=50  # ❌ Hardcoded limit
)

# After  
prs = await self.client.list_pull_requests(
    self._repository,
    state="all",
    limit=None  # ✅ Fetch all PRs
)
```

**Files Modified:**
- `psychic-fortnight/app/ingestion/github/ingestion.py` - Changed `limit=50` to `limit=None` for both PRs and issues
- `psychic-fortnight/app/ingestion/github/client.py` - Updated type hints to accept `int | None` for limit parameter

**Impact:** Now fetches ALL PRs and issues from the repository, not just the first 50 of each.

---

### 2. No Automatic Extraction ✅

**Problem:** After ingestion completed, items sat in the queue with no way to process them automatically.

**Solution:** Added extraction functionality with UI button.

**Changes Made:**

1. **Added `start_extraction()` method to BackendAPI** (`app/ui/utils/api.py`)
   ```python
   def start_extraction(self) -> Tuple[bool, str]:
       """Start extraction process for queued items."""
       # Creates background thread
       # Initializes ExtractionWorker
       # Processes all queued items
       # Returns success/failure message
   ```

2. **Added "Start Extraction" button to Processing Dashboard** (`app/ui/pages/2_Processing_Dashboard.py`)
   - Button appears when queue has pending items
   - Starts extraction worker in background thread
   - Shows progress and status updates

**How It Works:**
```
User clicks "Start Extraction"
    ↓
BackendAPI.start_extraction() creates background thread
    ↓
ExtractionWorker processes queue items
    ↓
Extractors analyze raw data
    ↓
Memory artifacts stored in JSON store
    ↓
UI shows extraction statistics
```

---

### 3. Improved Queue Display ✅

**Problem:** Queue items showed as generic dictionaries with unclear information.

**Fix:** Enhanced display to show meaningful information:

```python
# Before
st.text(f"• {item.get('item_id', 'Unknown')} - {item.get('item_type', 'Unknown')}")

# After
item_type = item.get('item_type', 'Unknown').upper()
item_num = item.get('item_number', '?')
source = item.get('source_id', 'Unknown')
st.text(f"• {source} - {item_type} #{item_num}")
```

**Example Output:**
```
• facebook_react - PR #12345
• facebook_react - ISSUE #67890
• microsoft_vscode - PR #54321
```

---

## Complete Workflow Now

### Step 1: Ingestion
1. User configures GitHub token and repository
2. User clicks "Start Ingestion"
3. System discovers ALL PRs and issues (no limit)
4. System fetches raw data for each item
5. System stores raw data with provenance
6. System enqueues items for extraction

### Step 2: Extraction
1. User sees pending items in queue
2. User clicks "Start Extraction" button
3. System processes queue items in background
4. Extractors analyze raw data
5. Memory artifacts created and stored
6. Statistics updated in UI

### Step 3: Indexing (Future)
1. Artifacts indexed to vector store
2. Knowledge graph updated
3. Ready for querying

---

## Files Modified

1. **`psychic-fortnight/app/ingestion/github/ingestion.py`**
   - Changed PR discovery limit from 50 to None
   - Changed issue discovery limit from 50 to None
   - Added logging for discovery progress

2. **`psychic-fortnight/app/ingestion/github/client.py`**
   - Updated `list_pull_requests()` type hint: `limit: int | None = 50`
   - Updated `list_issues()` type hint: `limit: int | None = 50`
   - Added documentation for limit parameter

3. **`psychic-fortnight/app/ui/utils/api.py`**
   - Added `start_extraction()` method
   - Implements background thread for extraction
   - Proper error handling and logging

4. **`psychic-fortnight/app/ui/pages/2_Processing_Dashboard.py`**
   - Improved queue item display format
   - Added "Start Extraction" button
   - Added helpful info messages

---

## Testing Checklist

### Ingestion Testing
- [ ] Configure GitHub token for large repository (2000+ items)
- [ ] Start ingestion
- [ ] Verify ALL items are discovered (not just 100)
- [ ] Check logs for "Discovered X pull requests" and "Discovered Y issues"
- [ ] Verify progress updates in UI
- [ ] Confirm all items stored successfully

### Extraction Testing
- [ ] Verify queue shows pending items after ingestion
- [ ] Click "Start Extraction" button
- [ ] Verify extraction starts in background
- [ ] Check logs for extraction progress
- [ ] Verify artifacts are created in data/extracted/
- [ ] Confirm extraction statistics update in UI

### End-to-End Testing
- [ ] Complete ingestion of real repository
- [ ] Start extraction immediately after
- [ ] Verify all steps complete successfully
- [ ] Check final artifact counts
- [ ] Verify no items left in queue

---

## Performance Considerations

### Large Repositories
- **Discovery:** May take several minutes for repos with 1000+ items
