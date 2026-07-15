#!/usr/bin/env python3
"""
Release Notes Generator

Generates release notes by analyzing Git commits, mapping them to PRs,
and categorizing changes based on labels and commit conventions.
Now includes git diff analysis to provide detailed insights about code changes.

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


# Category mappings based on labels and commit prefixes
CATEGORY_CONFIG = {
    "features": {
        "labels": ["feature", "enhancement", "new-feature"],
        "commit_prefixes": ["feat", "feature"],
        "emoji": "🚀"
    },
    "bug_fixes": {
        "labels": ["bug", "bugfix", "fix"],
        "commit_prefixes": ["fix", "bugfix"],
        "emoji": "🐛"
    },
    "technical": {
        "labels": ["refactor", "chore", "technical", "dependencies"],
        "commit_prefixes": ["refactor", "chore", "deps", "build", "ci"],
        "emoji": "⚙️"
    },
    "database": {
        "labels": ["database", "db", "migration"],
        "commit_prefixes": ["db", "migration"],
        "emoji": "📦"
    },
    "documentation": {
        "labels": ["documentation", "docs"],
        "commit_prefixes": ["docs", "doc"],
        "emoji": "📚"
    },
    "tests": {
        "labels": ["test", "testing"],
        "commit_prefixes": ["test"],
        "emoji": "✅"
    }
}

# Risk indicators
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


def get_commits_in_range(from_date: str, to_date: str) -> list[dict]:
    """Get commits within the specified date range."""
    since = f"{from_date}T00:00:00"
    until = f"{to_date}T23:59:59"
    
    cmd = [
        "git", "log",
        f"--since={since}",
        f"--until={until}",
        "--pretty=format:%H|%s|%an|%ae",
        "--reverse"
    ]
    
    output = run_command(cmd)
    commits = []
    
    for line in output.split('\n'):
        if line.strip():
            parts = line.split('|', 3)
            if len(parts) >= 3:
                commits.append({
                    'sha': parts[0],
                    'message': parts[1],
                    'author_name': parts[2],
                    'author_email': parts[3] if len(parts) > 3 else ''
                })
    
    return commits


def get_diff_for_commit(sha: str) -> str:
    """Get the full diff for a specific commit."""
    cmd = [
        "git", "diff",
        f"{sha}^..{sha}",
        "--stat"
    ]
    
    try:
        output = run_command(cmd)
        return output
    except RuntimeError:
        # For initial commits or edge cases
        cmd = ["git", "show", sha, "--stat"]
        return run_command(cmd)


def get_full_diff_for_commit(sha: str) -> str:
    """Get the complete diff with content for a specific commit."""
    cmd = [
        "git", "show",
        sha,
        "--format=",  # No commit metadata
        "--unified=0"  # Minimal context
    ]
    
    try:
        output = run_command(cmd)
        return output
    except RuntimeError:
        return ""


def analyze_code_changes(diff_content: str, commit_message: str) -> dict:
    """
    Analyze code changes from diff to extract meaningful information.
    
    Returns a dict with:
    - files_changed: list of files modified
    - additions: number of lines added
    - deletions: number of lines removed
    - key_changes: summary of significant changes
    - affected_components: inferred components/modules
    """
    result = {
        'files_changed': [],
        'additions': 0,
        'deletions': 0,
        'key_changes': [],
        'affected_components': set()
    }
    
    if not diff_content:
        return result
    
    lines = diff_content.split('\n')
    current_file = None
    
    for line in lines:
        # Track file changes - improved pattern matching
        if line.startswith('diff --git'):
            # Extract filename from diff header (handle both a/ and b/ prefixes)
            matches = re.findall(r'[ab]/([^\s]+)', line)
            if matches:
                # Use the second match (b/ side) as it's the new file
                current_file = matches[-1] if len(matches) > 1 else matches[0]
                # Avoid duplicates
                if current_file not in result['files_changed']:
                    result['files_changed'].append(current_file)
        
        # Count additions and deletions
        elif line.startswith('+') and not line.startswith('+++'):
            result['additions'] += 1
        elif line.startswith('-') and not line.startswith('---'):
            result['deletions'] += 1
        
        # Detect significant patterns in added lines
        if line.startswith('+') and not line.startswith('+++'):
            line_lower = line.lower()
            
            # Skip detection in comments, imports, and common non-functional code
            if line.strip().startswith('#') or line.strip().startswith('//') or line.strip().startswith('*'):
                continue
            
            # API changes - look for actual API definitions
            if re.search(r'(api|endpoint)\s*(=|:|def|route)', line_lower):
                result['key_changes'].append('API modification detected')
            
            # Database changes - look for actual DB operations
            if re.search(r'(migration|schema|table|database)\s*(create|alter|drop|modify)', line_lower):
                result['key_changes'].append('Database schema change detected')
            
            # Configuration changes - look for config definitions
            if re.search(r'(config|setting)\s*(=|:|load|get)', line_lower) and 'import' not in line_lower:
                result['key_changes'].append('Configuration change detected')
            
            # UI/Frontend changes - look for component definitions
            if any(re.search(rf'{x}\s*(=|:|<|def)', line_lower) for x in ['component', 'ui', 'frontend']):
                result['key_changes'].append('UI/Frontend change detected')
            
            # Test changes - look for test functions/classes
            if re.search(r'test\s*(def|class|func|it|describe)', line_lower):
                result['key_changes'].append('Test modification detected')
    
    # Infer affected components from file paths
    for file_path in result['files_changed']:
        # Clean up file path (remove any git diff artifacts)
        clean_path = file_path.split()[-1] if ' ' in file_path else file_path
        parts = clean_path.split('/')
        if len(parts) > 1:
            result['affected_components'].add(parts[0])
        if len(parts) > 2:
            result['affected_components'].add(f"{parts[0]}/{parts[1]}")
    
    result['affected_components'] = list(result['affected_components'])
    
    # Deduplicate key_changes while preserving order
    seen = set()
    unique_key_changes = []
    for change in result['key_changes']:
        if change not in seen:
            seen.add(change)
            unique_key_changes.append(change)
    result['key_changes'] = unique_key_changes
    
    return result


def get_pr_for_commit(gh: Github, repo_name: str, sha: str) -> Optional[dict]:
    """Get the pull request associated with a commit."""
    try:
        repo = gh.get_repo(repo_name)
        # Search for PRs that contain this commit
        pulls = repo.get_pulls(state='all')
        
        for pr in pulls:
            try:
                commits = pr.get_commits()
                for commit in commits:
                    if commit.sha == sha:
                        return {
                            'number': pr.number,
                            'title': pr.title,
                            'author': pr.user.login,
                            'labels': [label.name for label in pr.labels],
                            'body': pr.body or '',
                            'merged_at': str(pr.merged_at) if pr.merged_at else None
                        }
            except Exception:
                continue
        
        # Fallback: use GitHub API directly
        token = os.environ.get('GH_TOKEN', os.environ.get('GITHUB_TOKEN', ''))
        if token:
            headers = {'Authorization': f'token {token}'}
            url = f"https://api.github.com/repos/{repo_name}/commits/{sha}/pulls"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    pr_data = data[0]
                    return {
                        'number': pr_data['number'],
                        'title': pr_data['title'],
                        'author': pr_data['user']['login'],
                        'labels': [label['name'] for label in pr_data.get('labels', [])],
                        'body': pr_data.get('body', ''),
                        'merged_at': pr_data.get('merged_at')
                    }
    except Exception as e:
        print(f"Warning: Could not fetch PR for commit {sha[:8]}: {e}")
    
    return None


def extract_ticket_id(text: str) -> Optional[str]:
    """Extract ticket/issue ID from text (e.g., ABC-123)."""
    patterns = [
        r'[A-Z]+-\d+',  # Jira-style: ABC-123
        r'#\d+',         # GitHub issue: #123
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group()
    
    return None


def categorize_change(pr: dict, commit_message: str) -> str:
    """Categorize a change based on PR labels and commit message."""
    labels_lower = [label.lower() for label in pr.get('labels', [])]
    commit_lower = commit_message.lower()
    
    # Check labels first
    for category, config in CATEGORY_CONFIG.items():
        for label in config['labels']:
            if label in labels_lower:
                return category
    
    # Check commit prefixes
    for category, config in CATEGORY_CONFIG.items():
        for prefix in config['commit_prefixes']:
            if commit_lower.startswith(f"{prefix}(") or commit_lower.startswith(f"{prefix}:"):
                return category
    
    # Default to technical changes
    return "technical"


def detect_risks(pr: dict, commit_message: str) -> list[str]:
    """Detect potential risks or breaking changes."""
    risks = []
    text = f"{pr.get('title', '')} {pr.get('body', '')} {commit_message}".lower()
    
    for indicator in RISK_INDICATORS:
        if indicator in text:
            risks.append(f"Potential {indicator} detected")
    
    # Check for specific risk patterns
    if re.search(r'drop\s+table|alter\s+column|rename', text, re.IGNORECASE):
        risks.append("Database schema modification detected")
    
    if re.search(r'remove|delete|deprecat', text, re.IGNORECASE):
        risks.append("Removal or deprecation detected")
    
    return risks


def format_change_entry(pr: dict, commit_message: str, ticket_id: Optional[str], 
                       code_analysis: Optional[dict] = None) -> str:
    """Format a single change entry for the release notes."""
    title = pr.get('title', commit_message)
    number = pr.get('number')
    author = pr.get('author', 'Unknown')
    
    # Build the entry
    entry_parts = []
    
    if ticket_id:
        entry_parts.append(f"{ticket_id}:")
    
    entry_parts.append(title)
    
    if number:
        entry_parts.append(f"(#{number})")
    
    entry = " ".join(entry_parts)
    
    # Add code analysis insights if available
    if code_analysis:
        details = []
        
        # Add files changed summary
        files_changed = code_analysis.get('files_changed', [])
        if files_changed:
            if len(files_changed) == 1:
                details.append(f"Modified: {files_changed[0]}")
            elif len(files_changed) <= 3:
                details.append(f"Modified: {', '.join(files_changed)}")
            else:
                details.append(f"Modified: {len(files_changed)} files")
        
        # Add line changes
        additions = code_analysis.get('additions', 0)
        deletions = code_analysis.get('deletions', 0)
        if additions > 0 or deletions > 0:
            details.append(f"+{additions}/-{deletions} lines")
        
        # Add key changes detected
        key_changes = code_analysis.get('key_changes', [])
        if key_changes:
            unique_changes = list(set(key_changes))[:2]  # Limit to 2 most relevant
            if unique_changes:
                details.append(f"[{', '.join(unique_changes)}]")
        
        if details:
            entry += f" - {'; '.join(details)}"
    
    # Add author info optionally
    # entry += f" by @{author}"
    
    return entry


def generate_markdown(changes: dict, environment: str, date_from: str, date_to: str) -> str:
    """Generate Markdown release notes."""
    lines = []
    
    # Header
    lines.append(f"# {environment.upper()} Release Notes")
    lines.append(f"**Period:** {date_from} to {date_to}")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Summary
    total_changes = sum(len(items) for items in changes.values())
    lines.append(f"**Total Changes:** {total_changes}")
    lines.append("")
    
    # Categories in order
    category_order = ["features", "bug_fixes", "technical", "database", "documentation", "tests"]
    
    for category in category_order:
        items = changes.get(category, [])
        if not items:
            continue
        
        config = CATEGORY_CONFIG.get(category, {"emoji": "📝"})
        emoji = config["emoji"]
        
        # Category header
        category_name = category.replace("_", " ").title()
        lines.append(f"## {emoji} {category_name}")
        lines.append("")
        
        for item in items:
            lines.append(f"- {item}")
        
        lines.append("")
    
    # Known risks section
    all_risks = []
    for items in changes.get('_risks', {}).values():
        all_risks.extend(items)
    
    if all_risks:
        lines.append("## ⚠️ Known Risks / Breaking Changes")
        lines.append("")
        for risk in set(all_risks):
            lines.append(f"- {risk}")
        lines.append("")
    
    # Footer
    lines.append("---")
    lines.append("*Generated automatically by Release Notes Generator*")
    
    return "\n".join(lines)


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
    gh = Github(token) if token else None
    
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
    
    # Get commits in range
    print("Fetching commits...")
    commits = get_commits_in_range(args.date_from, args.date_to)
    print(f"Found {len(commits)} commits")
    
    if not commits:
        print("No commits found in the specified date range.")
        # Still generate empty release notes
        changes = {}
    else:
        # Process each commit
        changes = {category: [] for category in CATEGORY_CONFIG.keys()}
        changes['_risks'] = {}
        
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
                    'author': commit['author_name'],
                    'labels': [],
                    'body': ''
                }
            
            # Extract ticket ID
            ticket_id = extract_ticket_id(message) or extract_ticket_id(pr.get('title', ''))
            
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
            entry = format_change_entry(pr, message, ticket_id, code_analysis)
            changes[category].append(entry)
            
            # Detect risks (including from code analysis)
            risks = detect_risks(pr, message)
            if code_analysis.get('key_changes'):
                for change in code_analysis['key_changes']:
                    if 'schema' in change.lower() or 'breaking' in change.lower():
                        risks.append(change)
            if risks:
                changes['_risks'][sha] = risks
        
        # Optional AI enhancement
        if args.use_ai:
            print("\nApplying AI enhancement...")
            changes = enhance_with_ai(changes, args.environment)
    
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
