#!/usr/bin/env python3
"""
Release Notes Generator (v2.0)

Generates release notes by analyzing actual code changes from merged PRs
within a date range. Uses git diff at PR level and AI summarization.

Architecture:
1. Find all merged PRs in date range
2. For each PR: git diff base...head
3. Send diffs to LLM for intelligent summarization
4. Generate human-readable release notes

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
from collections import defaultdict

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


def get_merged_prs_in_range(gh: Github, repo_name: str, from_date: str, to_date: str) -> list[dict]:
    """Get all merged PRs within the specified date range."""
    print(f"Fetching merged PRs from {from_date} to {to_date}...")
    
    try:
        repo = gh.get_repo(repo_name)
        
        # Get all closed PRs (which includes merged ones)
        pulls = repo.get_pulls(state='closed', sort='updated', direction='desc')
        
        merged_prs = []
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        
        for pr in pulls:
            # Check if PR was merged and within date range
            if pr.merged_at:
                merged_dt = pr.merged_at.replace(tzinfo=None)
                if from_dt <= merged_dt <= to_dt:
                    merged_prs.append({
                        'number': pr.number,
                        'title': pr.title,
                        'author': pr.user.login,
                        'labels': [label.name for label in pr.labels],
                        'body': pr.body or '',
                        'merged_at': merged_dt,
                        'base_ref': pr.base.ref,
                        'head_ref': pr.head.ref,
                        'head_sha': pr.head.sha
                    })
        
        # Sort by merge date ascending
        merged_prs.sort(key=lambda x: x['merged_at'])
        
        print(f"Found {len(merged_prs)} merged PRs")
        return merged_prs
        
    except Exception as e:
        print(f"Error fetching PRs: {e}")
        return []


def get_diff_for_pr(base_ref: str, head_ref: str) -> dict:
    """Get git diff between base and head refs for a PR.
    
    Returns dict with:
    - files_changed: list of file paths
    - additions: total lines added
    - deletions: total lines removed
    - diff_content: full diff text
    """
    try:
        # Get diff stats
        stat_cmd = ["git", "diff", f"{base_ref}...{head_ref}", "--stat"]
        stat_output = run_command(stat_cmd)
        
        # Get full diff
        diff_cmd = ["git", "diff", f"{base_ref}...{head_ref}", "--unified=3"]
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
        
        return {
            'files_changed': files_changed,
            'additions': additions,
            'deletions': deletions,
            'diff_content': diff_content[:50000]  # Limit size for API calls
        }
        
    except Exception as e:
        print(f"Warning: Could not get diff: {e}")
        return {
            'files_changed': [],
            'additions': 0,
            'deletions': 0,
            'diff_content': ''
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


def summarize_with_llm(pr_data: dict, diff_data: dict, api_endpoint: Optional[str] = None) -> dict:
    """
    Send PR diff to LLM for intelligent summarization.
    
    Args:
        pr_data: PR metadata (title, labels, etc.)
        diff_data: Git diff data (files, additions, deletions, content)
        api_endpoint: Optional LLM API endpoint
    
    Returns:
        dict with:
        - summary: human-readable bullet points
        - category: suggested category
        - risks: any breaking changes or risks
    """
    
    # Build prompt for LLM
    files_changed = diff_data.get('files_changed', [])
    additions = diff_data.get('additions', 0)
    deletions = diff_data.get('deletions', 0)
    diff_content = diff_data.get('diff_content', '')
    
    prompt = f"""Analyze these code changes and generate release notes.

PR Title: {pr_data.get('title', 'Unknown')}
Labels: {', '.join(pr_data.get('labels', []))}

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

Output JSON format:
{{
    "summary": ["bullet point 1", "bullet point 2"],
    "category": "features|bug_fixes|technical|database|documentation|tests",
    "risks": ["risk 1"] or []
}}
"""
    
    # If no API endpoint, use simple heuristic-based fallback
    if not api_endpoint:
        return _heuristic_summary(pr_data, diff_data)
    
    # Call LLM API
    try:
        response = requests.post(
            api_endpoint,
            json={"prompt": prompt},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return {
                'summary': result.get('summary', [pr_data.get('title', 'Changes')]),
                'category': result.get('category', 'technical'),
                'risks': result.get('risks', [])
            }
    except Exception as e:
        print(f"LLM API call failed: {e}, using heuristic fallback")
    
    # Fallback to heuristic approach
    return _heuristic_summary(pr_data, diff_data)


def _heuristic_summary(pr_data: dict, diff_data: dict) -> dict:
    """Fallback heuristic-based summarization when LLM is not available."""
    
    title = pr_data.get('title', 'Changes')
    labels = [l.lower() for l in pr_data.get('labels', [])]
    files_changed = diff_data.get('files_changed', [])
    additions = diff_data.get('additions', 0)
    deletions = diff_data.get('deletions', 0)
    
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
    
    # Generate summary based on file types and changes
    summary_points = []
    
    # Check for specific file patterns
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
    
    # If no specific patterns detected, use title
    if not summary_points:
        summary_points.append(title)
    
    # Add stats if significant
    if additions > 100 or deletions > 50:
        summary_points.append(f"Significant refactoring (+{additions}/-{deletions} lines)")
    
    # Detect risks
    risks = []
    if has_db and deletions > 20:
        risks.append("Database migration may require careful testing")
    if any('remove' in title.lower() or 'deprecat' in title.lower()):
        risks.append("Potential breaking change or deprecation")
    
    return {
        'summary': summary_points,
        'category': category,
        'risks': risks
    }


def enhance_with_ai(changes: dict, environment: str) -> dict:
    """
    Optional AI enhancement step to rewrite technical descriptions
    into more human-readable format.
    
    This is a placeholder - in production, you would call an LLM API.
    """
    print("AI enhancement requested but not configured.")
    print("To enable AI summarization, configure an LLM API endpoint.")
    return changes


def main():
    parser = argparse.ArgumentParser(description="Generate release notes from Git history")
    parser.add_argument("--from", dest="date_from", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--environment", required=True, choices=["dev", "qa"], help="Target environment")
    parser.add_argument("--use-ai", dest="use_ai", action="store_true", help="Use AI for summarization")
    parser.add_argument("--llm-api", dest="llm_api", default=None, help="LLM API endpoint for intelligent summarization")
    parser.add_argument("--output", default="release-notes.md", help="Output file path")
    
    args = parser.parse_args()
    
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
    
    # NEW APPROACH: Work with merged PRs instead of individual commits
    if gh and repo_name:
        print("\n=== Using PR-based analysis (v2.0) ===")
        merged_prs = get_merged_prs_in_range(gh, repo_name, args.date_from, args.date_to)
        
        if not merged_prs:
            print("No merged PRs found in the specified date range.")
            changes = {category: [] for category in CATEGORY_CONFIG.keys()}
            changes['_risks'] = []
        else:
            # Process each PR
            changes = {category: [] for category in CATEGORY_CONFIG.keys()}
            changes['_risks'] = []
            
            for i, pr in enumerate(merged_prs, 1):
                print(f"\n[{i}/{len(merged_prs)}] Processing PR #{pr['number']}: {pr['title']}")
                
                # Get diff for this PR
                try:
                    diff_data = get_diff_for_pr(pr['base_ref'], pr['head_ref'])
                    print(f"  Files changed: {len(diff_data['files_changed'])}, +{diff_data['additions']}/-{diff_data['deletions']} lines")
                except Exception as e:
                    print(f"  Warning: Could not get diff: {e}")
                    diff_data = {'files_changed': [], 'additions': 0, 'deletions': 0, 'diff_content': ''}
                
                # Summarize with LLM or heuristics
                llm_endpoint = args.llm_api if args.use_ai else None
                summary_result = summarize_with_llm(pr, diff_data, api_endpoint=llm_endpoint)
                
                # Add summary points to appropriate category
                category = summary_result.get('category', 'technical')
                for point in summary_result.get('summary', [pr['title']]):
                    changes[category].append(point)
                
                # Collect risks
                changes['_risks'].extend(summary_result.get('risks', []))
    
    else:
        # Fallback to old commit-based approach if no GitHub access
        print("\n=== Falling back to commit-based analysis (legacy mode) ===")
        commits = get_commits_in_range(args.date_from, args.date_to)
        print(f"Found {len(commits)} commits")
        
        if not commits:
            print("No commits found in the specified date range.")
            changes = {category: [] for category in CATEGORY_CONFIG.keys()}
            changes['_risks'] = []
        else:
            # Process each commit (legacy approach)
            changes = {category: [] for category in CATEGORY_CONFIG.keys()}
            changes['_risks'] = []
            
            for i, commit in enumerate(commits, 1):
                sha = commit['sha']
                message = commit['message']
                
                print(f"[{i}/{len(commits)}] Processing commit {sha[:8]}: {message[:50]}...")
                
                # Try to get PR information
                pr = None
                if gh and repo_name:
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
                if code_analysis['key_changes']:
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
                if code_analysis.get('key_changes'):
                    for change in code_analysis['key_changes']:
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
