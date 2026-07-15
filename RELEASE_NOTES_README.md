# Release Notes Generator

Automated release notes generation using GitHub Actions and Python. This tool analyzes Git commits, maps them to pull requests, categorizes changes, and generates structured Markdown release notes.

## Features

- **Date Range Selection**: Generate notes for any time period
- **Environment Targeting**: Separate notes for dev and QA environments  
- **Automatic Categorization**: Changes sorted by type (Features, Bug Fixes, Technical, etc.)
- **PR Integration**: Maps commits to pull requests with labels and metadata
- **Ticket ID Extraction**: Automatically detects Jira/GitHub issue references
- **Risk Detection**: Identifies potential breaking changes and migrations
- **AI Enhancement Ready**: Optional LLM integration for human-readable summaries

## Architecture

```
GitHub Action (workflow_dispatch)
         ↓
Python Script (generate_release_notes.py)
         ↓
Git Log → Commits in Date Range
         ↓
GitHub API → Pull Request Metadata
         ↓
Categorization Engine → Labels + Commit Conventions
         ↓
Markdown Generator → Structured Release Notes
         ↓
GitHub Summary + Artifact Upload
```

## Usage

### Manual Workflow Dispatch

1. Go to **Actions** tab in your repository
2. Select **Generate Release Notes** workflow
3. Click **Run workflow**
4. Fill in parameters:
   - **Start date**: `YYYY-MM-DD` format
   - **End date**: `YYYY-MM-DD` format
   - **Environment**: `dev` or `qa`
   - **Use AI summarization**: Enable for enhanced descriptions (requires API configuration)

### Command Line (Local Testing)

```bash
# Install dependencies
pip install PyGithub requests

# Run the generator
python scripts/generate_release_notes.py \
  --from 2026-07-01 \
  --to 2026-07-14 \
  --environment qa

# With AI enhancement (placeholder)
python scripts/generate_release_notes.py \
  --from 2026-07-01 \
  --to 2026-07-14 \
  --environment qa \
  --use-ai
```

## Output Example

```markdown
# QA Release Notes
**Period:** 2026-07-01 to 2026-07-14
**Generated:** 2026-07-15 10:30:00

**Total Changes:** 12

## 🚀 Features
- ABC-123: Added customer export functionality (#456)
- DEF-456: Implemented batch processing API (#461)

## 🐛 Bug Fixes
- ABC-145: Fixed timeout during bulk upload (#462)
- GHI-789: Resolved memory leak in session handler (#468)

## ⚙️ Technical Changes
- Upgraded authentication library (#470)
- Refactored database connection pooling (#475)

## 📦 Database Changes
- Added index to customer_events table (#473)

## ⚠️ Known Risks / Breaking Changes
- Potential breaking detected
- Authentication token expiration behavior changed
```

## Configuration

### Category Mapping

Edit `CATEGORY_CONFIG` in the script to customize categorization:

```python
CATEGORY_CONFIG = {
    "features": {
        "labels": ["feature", "enhancement"],
        "commit_prefixes": ["feat", "feature"],
        "emoji": "🚀"
    },
    "bug_fixes": {
        "labels": ["bug", "fix"],
        "commit_prefixes": ["fix", "bugfix"],
        "emoji": "🐛"
    },
    # ... more categories
}
```

### Label-Based Categorization

The script checks PR labels first, then commit message prefixes:

| Label | Commit Prefix | Category |
|-------|--------------|----------|
| `feature`, `enhancement` | `feat:`, `feature:` | Features |
| `bug`, `fix` | `fix:`, `bugfix:` | Bug Fixes |
| `refactor`, `chore` | `refactor:`, `chore:` | Technical |
| `database`, `migration` | `db:`, `migration:` | Database |
| `documentation` | `docs:` | Documentation |
| `test` | `test:` | Tests |

## Environment-Specific Accuracy

For the most accurate environment-specific release notes, consider these approaches:

1. **Best**: Compare deployed SHAs
   ```bash
   git log previous_deployed_sha..current_deployed_sha
   ```

2. **Good**: Use release tags
   ```bash
   git log qa-v1.24..qa-v1.25
   ```

3. **Fallback**: Date-based (current implementation)
   ```bash
   git log --since="2026-07-01" --until="2026-07-14"
   ```

## AI Enhancement

The `--use-ai` flag enables optional LLM-powered summarization. To implement:

1. Configure your LLM API endpoint
2. Modify `enhance_with_ai()` function to call the API
3. Pass structured change data for rewriting

Example transformation:

**Before:**
> `fix(auth): handle null refresh token`

**After AI Enhancement:**
> **Authentication:** Fixed an issue where users could be unexpectedly logged out when a refresh token was unavailable. QA should verify login persistence and token refresh scenarios.

## Artifacts

Generated release notes are:
- Displayed in workflow output
- Published to GitHub Step Summary
- Uploaded as downloadable artifact (`release-notes-{environment}-{date}.md`)

## Permissions Required

The workflow requires:
- `contents: write` - For creating releases (optional)
- `pull-requests: read` - For fetching PR metadata

## Troubleshooting

### No commits found
- Verify date range contains merged commits
- Check that `fetch-depth: 0` is set in checkout step

### PR lookup failing
- Ensure `GITHUB_TOKEN` has appropriate permissions
- Verify repository name detection

### Missing categories
- Add relevant labels to your PRs
- Use conventional commit prefixes

## License

MIT
