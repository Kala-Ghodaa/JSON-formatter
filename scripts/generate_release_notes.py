#!/usr/bin/env python3
"""
Release Notes Generator (v2.1)

Generates release notes by analyzing actual code changes from merged PRs
within a date range. Uses git diff at PR level and AI summarization.

Architecture:
1. Find all merged PRs in date range (via GitHub Search API)
2. For each PR: git diff base_sha...head_sha
3. Send diffs to LLM for intelligent summarization (or fall back to heuristics)
4. Generate human-readable release notes

Falls back to a commit-based analysis when no GitHub token/repo is available.

Usage:
    python generate_release_notes.py --from 2026-07-01 --to 2026-07-14 --environment qa
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Optional

try:
    from github import Github
except ImportError:
    print("Installing PyGithub...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PyGithub", "-q"])
    from github import Github

import requests


# Category mappings for organizing output
CATEGORY_CONFIG = {
    "features": {"emoji": "🚀", "label": "Features"},
    "bug_fixes": {"emoji": "🐛", "label": "Bug Fixes"},
    "technical": {"emoji": "⚙️", "label": "Technical"},
    "database": {"emoji": "📦", "label": "Database"},
    "documentation": {"emoji": "📚", "label": "Documentation"},
    "tests": {"emoji": "✅", "label": "Tests"},
}

# Risk indicators for breaking changes
RISK_INDICATORS = [
    "breaking", "deprecated", "removed", "migration",
    "schema change", "api change", "backward incompatible"
]

# Markers delimiting the auto-generated summary block inside a PR body. Text
# outside these markers (the author's own description) is always preserved.
RN_START = "<!-- RELEASE-NOTES:START -->"
RN_END = "<!-- RELEASE-NOTES:END -->"


def build_summary_block(summary_points: list[str], risks: list[str]) -> str:
    """Render the marked release-notes block for a PR body."""
    lines = [RN_START, "### 📝 Release Notes Summary", ""]
    for point in summary_points:
        lines.append(f"- {point}")
    if risks:
        lines.append("")
        lines.append("**⚠️ Risks / Breaking Changes:**")
        for risk in risks:
            lines.append(f"- {risk}")
    lines.append("")
    lines.append("_Auto-generated from the diff. Edit outside the markers freely._")
    lines.append(RN_END)
    return "\n".join(lines)


def upsert_summary_in_body(body: str, block: str) -> str:
    """Insert or replace the marked block in a PR body without touching the
    author's own text. Replaces between existing markers if both present,
    otherwise appends the block to the end."""
    body = body or ""
    if RN_START in body and RN_END in body:
        pre = body.split(RN_START, 1)[0]
        post = body.split(RN_END, 1)[1]
        return f"{pre.rstrip()}\n\n{block}\n{post.lstrip()}".strip() + "\n"
    base = body.rstrip()
    return (f"{base}\n\n{block}" if base else block)


def extract_summary_block(body: str) -> str:
    """Return the text between the markers (without the markers), or ""."""
    body = body or ""
    if RN_START in body and RN_END in body:
        return body.split(RN_START, 1)[1].split(RN_END, 1)[0].strip()
    return ""


def run_command(cmd: list[str], cwd: Optional[str] = None) -> str:
    """Run a shell command and return the output."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or os.getcwd()
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def ensure_commit_available(sha: str) -> bool:
    """Make sure a commit is present in the local repo, fetching it from
    origin if necessary. Needed because PR head branches are often deleted
    after merge, so we diff against raw commit SHAs instead of branch refs."""
    check = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        capture_output=True
    )
    if check.returncode == 0:
        return True

    fetch = subprocess.run(
        ["git", "fetch", "--depth=1", "origin", sha],
        capture_output=True,
        text=True
    )
    return fetch.returncode == 0


def get_merged_prs_in_range(gh: Github, repo_name: str, from_date: str, to_date: str) -> list[dict]:
    """Get all merged PRs within the specified date range.

    Uses the GitHub Search API with a `merged:` qualifier so filtering happens
    server-side, instead of paginating through the repo's entire closed-PR
    history on every run.
    """
    print(f"Fetching merged PRs from {from_date} to {to_date}...")

    from_dt = datetime.strptime(from_date, "%Y-%m-%d")
    to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    query = f"repo:{repo_name} is:pr is:merged merged:{from_date}..{to_date}"

    merged_prs = []
    try:
        issues = gh.search_issues(query)

        for issue in issues:
            try:
                pr = issue.as_pull_request()
            except Exception as e:
                print(f"  Warning: could not load PR for #{issue.number}: {e}")
                continue

            if not pr.merged_at:
                continue

            merged_dt = pr.merged_at.replace(tzinfo=None)
            if not (from_dt <= merged_dt <= to_dt):
                continue

            merged_prs.append({
                'number': pr.number,
                'title': pr.title,
                'author': pr.user.login,
                'labels': [label.name for label in pr.labels],
                'body': pr.body or '',
                'merged_at': merged_dt,
                'base_ref': pr.base.ref,
                'base_sha': pr.base.sha,
                'head_ref': pr.head.ref,
                'head_sha': pr.head.sha
            })

        merged_prs.sort(key=lambda x: x['merged_at'])

        print(f"Found {len(merged_prs)} merged PRs")
        return merged_prs

    except Exception as e:
        print(f"Error fetching PRs: {e}")
        return []


def get_diff_for_pr(base_sha: str, head_sha: str) -> dict:
    """Get git diff between a PR's base and head commit SHAs.

    Uses raw SHAs rather than branch names since head branches are commonly
    deleted after merge, and fetches them individually if not already present
    in the local clone.

    Returns dict with:
    - files_changed: list of file paths
    - additions: total lines added
    - deletions: total lines removed
    - diff_content: full diff text
    """
    try:
        for sha in (base_sha, head_sha):
            if not ensure_commit_available(sha):
                print(f"  Warning: could not fetch commit {sha[:8]}; diff may be incomplete")

        # Get diff stats
        stat_cmd = ["git", "diff", f"{base_sha}...{head_sha}", "--stat"]
        stat_output = run_command(stat_cmd)

        # Get full diff
        diff_cmd = ["git", "diff", f"{base_sha}...{head_sha}", "--unified=3"]
        diff_content = run_command(diff_cmd)

        # Parse file changes
        files_changed = []
        additions = 0
        deletions = 0

        for line in stat_output.split('\n'):
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 1:
                    filename = parts[0].strip()
                    if filename and not filename.startswith('diff'):
                        files_changed.append(filename)

            # Count additions/deletions from summary line
            if 'insertion' in line.lower() or 'deletion' in line.lower():
                add_match = re.search(r'(\d+)\s+insertion', line, re.IGNORECASE)
                del_match = re.search(r'(\d+)\s+deletion', line, re.IGNORECASE)
                if add_match:
                    additions += int(add_match.group(1))
                if del_match:
                    deletions += int(del_match.group(1))

        # Extract lightweight structural signal from the raw diff so the
        # heuristic fallback (used when AI summarization isn't configured or
        # fails) has something more concrete to report than a filename guess.
        new_files = re.findall(r'^diff --git a/\S+ b/(\S+)\nnew file mode', diff_content, re.MULTILINE)
        deleted_files = re.findall(r'^diff --git a/(\S+) b/\S+\ndeleted file mode', diff_content, re.MULTILINE)

        # Git includes the enclosing function/section name after the second
        # "@@" in a hunk header when it can detect one (e.g. "@@ -10,7 +10,9 @@ def foo():")
        raw_contexts = re.findall(r'^@@[^@]*@@[ \t]+(.+)$', diff_content, re.MULTILINE)
        hunk_contexts = []
        seen_contexts = set()
        for ctx in raw_contexts:
            ctx = ctx.strip()
            if ctx and ctx not in seen_contexts:
                seen_contexts.add(ctx)
                hunk_contexts.append(ctx)

        return {
            'files_changed': files_changed,
            'additions': additions,
            'deletions': deletions,
            'diff_content': diff_content[:50000],  # Limit size for API calls
            'new_files': new_files,
            'deleted_files': deleted_files,
            'hunk_contexts': hunk_contexts[:10]
        }

    except Exception as e:
        print(f"Warning: Could not get diff: {e}")
        return {
            'files_changed': [],
            'additions': 0,
            'deletions': 0,
            'diff_content': '',
            'new_files': [],
            'deleted_files': [],
            'hunk_contexts': []
        }


def generate_markdown(changes: dict, environment: str, date_from: str, date_to: str) -> str:
    """Generate Markdown release notes."""
    lines = []

    # Header
    lines.append(f"# {environment.upper()} Release Notes")
    lines.append(f"**Period:** {date_from} to {date_to}")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Summary
    total_changes = sum(len(items) for items in changes.values() if isinstance(items, list))
    lines.append(f"**Total Changes:** {total_changes}")
    lines.append("")

    # Categories in order
    category_order = ["features", "bug_fixes", "technical", "database", "documentation", "tests"]

    for category in category_order:
        items = changes.get(category, [])
        if not items or not isinstance(items, list):
            continue

        config = CATEGORY_CONFIG.get(category, {"emoji": "📝", "label": category.title()})
        emoji = config["emoji"]
        label = config["label"]

        # Category header
        lines.append(f"## {emoji} {label}")
        lines.append("")

        for item in items:
            lines.append(f"- {item}")

        lines.append("")

    # Known risks section
    all_risks = changes.get('_risks', [])

    if all_risks:
        lines.append("## ⚠️ Known Risks / Breaking Changes")
        lines.append("")
        for risk in set(all_risks):
            lines.append(f"- {risk}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("*Generated automatically by analyzing actual code changes*")

    return "\n".join(lines)


def summarize_with_llm(pr_data: dict, diff_data: dict, api_endpoint: Optional[str] = None,
                        api_key: Optional[str] = None, model: str = "openai/gpt-4o-mini",
                        existing_summary: str = "") -> dict:
    """
    Send PR diff to LLM for intelligent summarization.

    Args:
        pr_data: PR metadata (title, labels, etc.)
        diff_data: Git diff data (files, additions, deletions, content)
        existing_summary: Optional prior summary (e.g. from the PR body block).
            Passed to the model as a hint only; the diff remains the source of
            truth, so a stale block can't produce wrong notes.
        api_endpoint: Optional LLM API endpoint. Three contracts are supported:
            - Anthropic Messages API (endpoint contains "anthropic.com"):
              x-api-key auth, message format, content-block parsing.
            - OpenAI-compatible Chat Completions (GitHub Models
              "models.github.ai", any "openai" endpoint, or a URL ending in
              "/chat/completions"): Bearer auth, messages format,
              choices[0].message.content parsing.
            - Any other endpoint: the original {"prompt": ...} contract, so a
              custom summarization service still works unchanged.
        api_key: API key for the endpoint (required for Anthropic and
            OpenAI-compatible endpoints; for GitHub Models this is a token
            with `models: read`).
        model: Model id for OpenAI-compatible endpoints (default suits
            GitHub Models, e.g. "openai/gpt-4o-mini").

    Returns:
        dict with:
        - summary: human-readable bullet points
        - category: suggested category
        - risks: any breaking changes or risks
    """

    files_changed = diff_data.get('files_changed', [])
    additions = diff_data.get('additions', 0)
    deletions = diff_data.get('deletions', 0)
    diff_content = diff_data.get('diff_content', '')

    hint_block = ""
    if existing_summary.strip():
        hint_block = (
            "\nA prior summary exists (may be stale — use only as a hint, verify "
            "everything against the diff below):\n"
            f"{existing_summary.strip()}\n"
        )

    prompt = f"""Analyze these code changes and generate release notes.

PR Title: {pr_data.get('title', 'Unknown')}
Labels: {', '.join(pr_data.get('labels', []))}
{hint_block}
Files Changed ({len(files_changed)} files, +{additions}/-{deletions} lines):
{chr(10).join(files_changed[:20])}

Git Diff:
```
{diff_content[:10000]}
```

Generate release notes following these rules:
1. Focus on USER-VISIBLE changes and FEATURES
2. Don't mention commit hashes, line numbers, or technical implementation details
3. Group related changes together
4. Identify the category: features, bug_fixes, technical, database, documentation, or tests
5. Flag any BREAKING CHANGES or RISKS

Respond with ONLY a JSON object (no markdown fences, no other text) in this format:
{{
    "summary": ["bullet point 1", "bullet point 2"],
    "category": "features|bug_fixes|technical|database|documentation|tests",
    "risks": ["risk 1"] or []
}}
"""

    # If no API endpoint, use simple heuristic-based fallback
    if not api_endpoint:
        return _heuristic_summary(pr_data, diff_data)

    is_anthropic = "anthropic.com" in api_endpoint
    is_openai_compatible = (
        "models.github.ai" in api_endpoint
        or "openai" in api_endpoint
        or api_endpoint.rstrip("/").endswith("/chat/completions")
    )

    system_prompt = (
        "You respond with only a single valid JSON object matching the "
        "requested schema. No markdown fences, no commentary."
    )

    try:
        headers = {"Content-Type": "application/json"}

        if is_anthropic:
            if not api_key:
                raise ValueError(
                    "Anthropic endpoint requires an API key (--llm-api-key or ANTHROPIC_API_KEY)"
                )
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
            payload = {
                "model": "claude-sonnet-5",
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": [{"role": "user", "content": prompt}]
            }
        elif is_openai_compatible:
            if not api_key:
                raise ValueError(
                    "OpenAI-compatible endpoint requires an API key "
                    "(--llm-api-key; for GitHub Models use a token with models:read)"
                )
            headers["Authorization"] = f"Bearer {api_key}"
            payload = {
                "model": model,
                "max_tokens": 1024,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            }
        else:
            # Original custom contract, preserved for other endpoints
            payload = {"prompt": prompt}

        response = requests.post(api_endpoint, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if is_anthropic:
            text = "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
        elif is_openai_compatible:
            text = data["choices"][0]["message"]["content"]
        else:
            text = data if isinstance(data, str) else json.dumps(data)

        cleaned = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.MULTILINE).strip()
        result = json.loads(cleaned)

        return {
            'summary': result.get('summary', [pr_data.get('title', 'Changes')]),
            'category': result.get('category', 'technical'),
            'risks': result.get('risks', [])
        }

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        body = e.response.text[:300] if e.response is not None else ""
        print(f"  LLM API call failed: HTTP {status} - {body}")
    except Exception as e:
        print(f"  LLM API call failed: {e}")

    print("  Using heuristic fallback for this PR")

    # Fallback to heuristic approach
    return _heuristic_summary(pr_data, diff_data)


def _truncated_list(items: list[str], limit: int = 5) -> str:
    """Join a list for display, noting how many extra items were omitted."""
    shown = ", ".join(items[:limit])
    remaining = len(items) - limit
    if remaining > 0:
        shown += f", and {remaining} more"
    return shown


def _heuristic_summary(pr_data: dict, diff_data: dict) -> dict:
    """Fallback heuristic-based summarization when LLM is not available.

    NOTE: this is a mechanical fallback, not a real understanding of the
    change. It reports what files/functions were touched, which is far more
    useful than a raw PR title (especially for bots/agents that generate
    generic titles like "Update from task <uuid>"), but it still can't
    describe *why* a change was made or what it accomplishes for users.
    For that, use --use-ai with a working --llm-api endpoint.
    """

    title = pr_data.get('title', 'Changes')
    labels = [l.lower() for l in pr_data.get('labels', [])]
    files_changed = diff_data.get('files_changed', [])
    additions = diff_data.get('additions', 0)
    deletions = diff_data.get('deletions', 0)
    new_files = diff_data.get('new_files', [])
    deleted_files = diff_data.get('deleted_files', [])
    hunk_contexts = diff_data.get('hunk_contexts', [])

    # Determine category from labels
    category = 'technical'
    if any(l in ['feature', 'enhancement', 'new-feature'] for l in labels):
        category = 'features'
    elif any(l in ['bug', 'bugfix', 'fix'] for l in labels):
        category = 'bug_fixes'
    elif any(l in ['database', 'db', 'migration'] for l in labels):
        category = 'database'
    elif any(l in ['documentation', 'docs'] for l in labels):
        category = 'documentation'
    elif any(l in ['test', 'testing'] for l in labels):
        category = 'tests'

    summary_points = []

    # Prefer concrete signal pulled straight from the diff over filename
    # guessing: which files were added/removed, and which functions/sections
    # the hunks touched (git surfaces this in the "@@ ... @@ context" line
    # for most common languages).
    if new_files:
        summary_points.append(f"Added new file(s): {_truncated_list(new_files)}")
    if deleted_files:
        summary_points.append(f"Removed file(s): {_truncated_list(deleted_files)}")
    if hunk_contexts:
        summary_points.append(f"Changed areas: {_truncated_list(hunk_contexts, 6)}")

    # Only fall back to coarse filename-pattern guessing if the diff itself
    # gave us nothing more specific above
    if not summary_points:
        has_api = any('api' in f or 'route' in f or 'endpoint' in f for f in files_changed)
        has_db = any('migration' in f or 'schema' in f or 'model' in f for f in files_changed)
        has_ui = any('component' in f or 'ui' in f or 'page' in f or 'view' in f for f in files_changed)
        has_test = any('test' in f for f in files_changed)
        has_config = any('config' in f or 'setting' in f for f in files_changed)

        if has_api:
            summary_points.append("API endpoints modified")
        if has_db:
            summary_points.append("Database schema or models updated")
        if has_ui:
            summary_points.append("User interface improvements")
        if has_test:
            summary_points.append("Test coverage enhanced")
        if has_config:
            summary_points.append("Configuration updates")

    # Last resort: list the actual files touched rather than a possibly
    # meaningless title (e.g. autogenerated task IDs from a bot/agent)
    if not summary_points:
        if files_changed:
            summary_points.append(f"Modified {len(files_changed)} file(s): {_truncated_list(files_changed)}")
        else:
            summary_points.append(title)

    if additions > 100 or deletions > 50:
        summary_points.append(f"({additions} lines added, {deletions} removed)")

    # Detect risks
    risks = []
    if deletions > 20 and any('migration' in f or 'schema' in f for f in files_changed + new_files):
        risks.append("Database migration may require careful testing")
    if 'remove' in title.lower() or 'deprecat' in title.lower() or deleted_files:
        risks.append("Potential breaking change or deprecation")

    return {
        'summary': summary_points,
        'category': category,
        'risks': risks
    }


# --- Legacy commit-based path -------------------------------------------
# Used only when no GitHub token or repository could be resolved, so PR
# metadata isn't available. Works directly off local git history instead.

def get_commits_in_range(date_from: str, date_to: str) -> list[dict]:
    """Get commits on the current branch within the date range."""
    since = date_from
    until = f"{date_to} 23:59:59"
    log_format = "%H%x1f%an%x1f%aI%x1f%s"

    try:
        output = run_command(["git", "log", f"--since={since}", f"--until={until}",
                               f"--pretty=format:{log_format}"])
    except RuntimeError as e:
        print(f"Warning: git log failed: {e}")
        return []

    commits = []
    for line in output.split('\n'):
        if not line.strip():
            continue
        parts = line.split('\x1f')
        if len(parts) != 4:
            continue
        sha, author_name, iso_date, message = parts
        commits.append({'sha': sha, 'author_name': author_name, 'date': iso_date, 'message': message})

    commits.sort(key=lambda c: c['date'])
    return commits


def get_pr_for_commit(gh: Optional[Github], repo_name: str, sha: str) -> Optional[dict]:
    """Look up the PR associated with a commit, if GitHub API access happens
    to be available even though we're on the legacy path (e.g. a token is
    present but repo auto-detection failed)."""
    if not gh or not repo_name:
        return None
    try:
        repo = gh.get_repo(repo_name)
        commit = repo.get_commit(sha)
        for pr in commit.get_pulls():
            return {
                'number': pr.number,
                'title': pr.title,
                'author': pr.user.login,
                'labels': [label.name for label in pr.labels],
                'body': pr.body or ''
            }
    except Exception as e:
        print(f"  Warning: could not look up PR for commit {sha[:8]}: {e}")
    return None


def get_full_diff_for_commit(sha: str) -> str:
    """Get the diff introduced by a single commit."""
    try:
        return run_command(["git", "show", sha, "--unified=3", "--format="])[:50000]
    except RuntimeError as e:
        print(f"  Warning: could not get diff for commit {sha[:8]}: {e}")
        return ""


def analyze_code_changes(diff_content: str, message: str) -> dict:
    """Lightweight heuristic scan of a raw commit diff."""
    key_changes = []
    lower_msg = message.lower()

    if re.search(r'\+\+\+ .*(migration|schema)', diff_content, re.IGNORECASE) or 'schema' in lower_msg:
        key_changes.append("Database schema change")
    if re.search(r'\+\+\+ .*(route|api|endpoint)', diff_content, re.IGNORECASE) or 'api' in lower_msg:
        key_changes.append("API change")
    if re.search(r'\+\+\+ .*test', diff_content, re.IGNORECASE):
        key_changes.append("Test coverage change")
    if 'breaking' in diff_content.lower() or 'breaking' in lower_msg:
        key_changes.append("Breaking change flagged in diff/message")

    return {'key_changes': key_changes}


def categorize_change(pr: Optional[dict], message: str) -> str:
    """Categorize a change from PR labels (if any) or commit message keywords."""
    labels = [l.lower() for l in (pr.get('labels') if pr else []) or []]
    message_lower = message.lower()

    if any(l in ['feature', 'enhancement', 'new-feature'] for l in labels) or message_lower.startswith('feat'):
        return 'features'
    if any(l in ['bug', 'bugfix', 'fix'] for l in labels) or message_lower.startswith('fix'):
        return 'bug_fixes'
    if any(l in ['database', 'db', 'migration'] for l in labels):
        return 'database'
    if any(l in ['documentation', 'docs'] for l in labels) or message_lower.startswith('docs'):
        return 'documentation'
    if any(l in ['test', 'testing'] for l in labels) or message_lower.startswith('test'):
        return 'tests'
    return 'technical'


def format_change_entry(pr: Optional[dict], message: str, _unused, code_analysis: dict) -> str:
    """Format a single changelog line, preferring the PR title over the raw commit message."""
    title = (pr.get('title') if pr else None) or message
    entry = title.strip()
    if pr and pr.get('number'):
        entry += f" (#{pr['number']})"
    return entry


def detect_risks(pr: Optional[dict], message: str) -> list[str]:
    """Flag potential breaking changes based on known risk keywords."""
    title = (pr.get('title') if pr else '') or ''
    text = f"{title} {message}".lower()
    risks = []
    for indicator in RISK_INDICATORS:
        if indicator in text:
            label = title or message
            risks.append(f"Potential risk detected ('{indicator}') in \"{label[:60]}\"")
            break
    return risks

# --------------------------------------------------------------------------


def summarize_single_pr(gh: Github, repo_name: str, pr_number: int,
                        llm_endpoint: Optional[str], llm_key: Optional[str],
                        model: str) -> bool:
    """Summarize one PR from its diff and write the summary into the PR body
    (inside the marked block). Returns True on success."""
    try:
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
    except Exception as e:
        print(f"Error: could not load PR #{pr_number} from {repo_name}: {e}")
        return False

    print(f"Summarizing PR #{pr.number}: {pr.title}")

    pr_data = {
        'title': pr.title,
        'labels': [label.name for label in pr.labels],
        'body': pr.body or '',
    }

    diff_data = get_diff_for_pr(pr.base.sha, pr.head.sha)
    print(f"  Files changed: {len(diff_data['files_changed'])}, "
          f"+{diff_data['additions']}/-{diff_data['deletions']} lines")

    result = summarize_with_llm(pr_data, diff_data, api_endpoint=llm_endpoint,
                                api_key=llm_key, model=model)

    block = build_summary_block(result.get('summary', []), result.get('risks', []))
    new_body = upsert_summary_in_body(pr.body or "", block)

    if new_body == (pr.body or ""):
        print("  PR body already up to date; nothing to write.")
        return True

    try:
        pr.edit(body=new_body)
    except Exception as e:
        print(f"Error: could not update PR body: {e}")
        return False

    print("  ✓ Wrote release-notes summary into PR body")
    print("-" * 50)
    print(block)
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate release notes from Git history")
    parser.add_argument("--from", dest="date_from", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="End date (YYYY-MM-DD)")
    parser.add_argument("--environment", choices=["dev", "qa"], help="Target environment")
    parser.add_argument("--pr-number", dest="pr_number", type=int, default=None,
                         help="Summarize a single PR into its body instead of generating range notes")
    parser.add_argument("--use-ai", dest="use_ai", action="store_true", help="Use AI for summarization")
    parser.add_argument("--llm-api", dest="llm_api", default=None, help="LLM API endpoint for intelligent summarization")
    parser.add_argument("--llm-api-key", dest="llm_api_key", default=None,
                         help="API key for the LLM endpoint (falls back to ANTHROPIC_API_KEY env var; "
                              "for GitHub Models, to GH_TOKEN/GITHUB_TOKEN)")
    parser.add_argument("--llm-model", dest="llm_model", default="openai/gpt-4o-mini",
                         help="Model id for OpenAI-compatible endpoints (default: openai/gpt-4o-mini)")
    parser.add_argument("--output", default="release-notes.md", help="Output file path")

    args = parser.parse_args()

    pr_mode = args.pr_number is not None

    if pr_mode:
        # In PR-summary mode range args are irrelevant; AI is always used.
        args.use_ai = True
    else:
        missing = [name for name, val in
                   (("--from", args.date_from), ("--to", args.date_to),
                    ("--environment", args.environment)) if not val]
        if missing:
            print(f"Error: {', '.join(missing)} required (or use --pr-number for single-PR mode)")
            sys.exit(1)

        # Validate dates
        try:
            datetime.strptime(args.date_from, "%Y-%m-%d")
            datetime.strptime(args.date_to, "%Y-%m-%d")
        except ValueError as e:
            print(f"Error: Invalid date format. Use YYYY-MM-DD. {e}")
            sys.exit(1)

        print(f"Generating release notes for {args.environment.upper()}")
        print(f"Date range: {args.date_from} to {args.date_to}")
        print("-" * 50)

    # Initialize GitHub client
    token = os.environ.get('GH_TOKEN', os.environ.get('GITHUB_TOKEN', ''))
    if not token:
        print("Warning: No GitHub token found. Set GH_TOKEN or GITHUB_TOKEN environment variable.")
        gh = None
    else:
        gh = Github(token)

    # Get repository name
    repo_name = os.environ.get('GITHUB_REPOSITORY', '')
    if not repo_name:
        # Fallback: get from git remote
        try:
            remote_url = run_command(["git", "remote", "get-url", "origin"])
            match = re.search(r'github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$', remote_url)
            if match:
                repo_name = match.group(1)
        except Exception:
            pass

    if not repo_name:
        print("Warning: Could not determine repository name. PR lookup may be limited.")

    GITHUB_MODELS_ENDPOINT = "https://models.github.ai/inference/chat/completions"

    llm_endpoint = None
    if args.use_ai:
        # If --use-ai is set but no endpoint given, default to GitHub Models
        # so the workflow can't silently degrade to heuristic mode again.
        llm_endpoint = args.llm_api or GITHUB_MODELS_ENDPOINT

    llm_key = args.llm_api_key or os.environ.get('ANTHROPIC_API_KEY')
    # GitHub Models authenticates with the same token as the API; fall back to
    # it when no explicit key was supplied.
    if llm_endpoint and "models.github.ai" in llm_endpoint and not llm_key:
        llm_key = token

    # Single-PR mode: summarize the PR and write it into the PR body, then exit.
    if pr_mode:
        if not gh or not repo_name:
            print("Error: PR-summary mode needs a GitHub token and repository.")
            sys.exit(1)
        ok = summarize_single_pr(gh, repo_name, args.pr_number,
                                 llm_endpoint, llm_key, args.llm_model)
        sys.exit(0 if ok else 1)

    if not llm_endpoint:
        print("\n" + "!" * 70)
        print("NOTE: Running WITHOUT AI summarization (heuristic mode only).")
        print("Summaries will list files/functions touched, not describe what")
        print("the change actually does. For real AI-written descriptions, run:")
        print("  --use-ai --llm-api https://api.anthropic.com/v1/messages \\")
        print("  --llm-api-key <your key>   (or set ANTHROPIC_API_KEY)")
        print("!" * 70)

    if gh and repo_name:
        print("\n=== Using PR-based analysis (v2.1) ===")
        merged_prs = get_merged_prs_in_range(gh, repo_name, args.date_from, args.date_to)

        changes = {category: [] for category in CATEGORY_CONFIG.keys()}
        changes['_risks'] = []

        if not merged_prs:
            print("No merged PRs found in the specified date range.")
        else:
            for i, pr in enumerate(merged_prs, 1):
                print(f"\n[{i}/{len(merged_prs)}] Processing PR #{pr['number']}: {pr['title']}")

                try:
                    diff_data = get_diff_for_pr(pr['base_sha'], pr['head_sha'])
                    print(f"  Files changed: {len(diff_data['files_changed'])}, "
                          f"+{diff_data['additions']}/-{diff_data['deletions']} lines")
                except Exception as e:
                    print(f"  Warning: Could not get diff: {e}")
                    diff_data = {'files_changed': [], 'additions': 0, 'deletions': 0, 'diff_content': ''}

                # Reuse any summary the PR-summary workflow already wrote into
                # the body as a hint; the diff stays the source of truth.
                prior_summary = extract_summary_block(pr.get('body', ''))

                summary_result = summarize_with_llm(pr, diff_data, api_endpoint=llm_endpoint,
                                                    api_key=llm_key, model=args.llm_model,
                                                    existing_summary=prior_summary)

                category = summary_result.get('category', 'technical')
                if category not in changes:
                    category = 'technical'
                for point in summary_result.get('summary', [pr['title']]):
                    changes[category].append(point)

                changes['_risks'].extend(summary_result.get('risks', []))

    else:
        # Fallback to commit-based approach if no GitHub access
        print("\n=== Falling back to commit-based analysis (legacy mode) ===")
        commits = get_commits_in_range(args.date_from, args.date_to)
        print(f"Found {len(commits)} commits")

        changes = {category: [] for category in CATEGORY_CONFIG.keys()}
        changes['_risks'] = []

        if not commits:
            print("No commits found in the specified date range.")
        else:
            for i, commit in enumerate(commits, 1):
                sha = commit['sha']
                message = commit['message']

                print(f"[{i}/{len(commits)}] Processing commit {sha[:8]}: {message[:50]}...")

                # Try to get PR information
                pr = get_pr_for_commit(gh, repo_name, sha)

                # If no PR found, create a minimal entry from commit
                if not pr:
                    pr = {
                        'number': None,
                        'title': message,
                        'author': commit.get('author_name', 'Unknown'),
                        'labels': [],
                        'body': ''
                    }

                # Get and analyze code diff
                print(f"  Analyzing code changes for {sha[:8]}...")
                diff_content = get_full_diff_for_commit(sha)
                code_analysis = analyze_code_changes(diff_content, message)

                # Categorize based on both PR labels and code analysis
                category = categorize_change(pr, message)

                # Override category if code analysis suggests otherwise
                key_changes_lower = [c.lower() for c in code_analysis['key_changes']]
                if any('database' in c for c in key_changes_lower):
                    category = 'database'
                elif any('api' in c for c in key_changes_lower):
                    category = 'features'
                elif any('test' in c for c in key_changes_lower):
                    category = 'tests'

                # Format entry with code analysis insights
                entry = format_change_entry(pr, message, None, code_analysis)
                changes[category].append(entry)

                # Detect risks (including from code analysis)
                risks = detect_risks(pr, message)
                for change in code_analysis.get('key_changes', []):
                    if 'schema' in change.lower() or 'breaking' in change.lower():
                        risks.append(change)
                if risks:
                    changes['_risks'].extend(risks)

    # Generate Markdown
    print("\nGenerating Markdown...")
    markdown = generate_markdown(changes, args.environment, args.date_from, args.date_to)

    # Write to file
    with open(args.output, 'w') as f:
        f.write(markdown)

    print(f"\n✓ Release notes written to {args.output}")
    print("\n" + "=" * 50)
    print(markdown)


if __name__ == "__main__":
    main()
