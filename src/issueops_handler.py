"""GitHub IssueOps handler for Awesome Android Games.

Parses issue form submissions and slash commands (/add, /remove) to automate
catalog additions, removals, and updates via GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure src directory is in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from update_stats import add_game, remove_game
from utils import parse_repo_url


def parse_issue_markdown_form(body: str) -> Dict[str, str]:
    """Extract key-value pairs from GitHub Issue Form markdown output.

    GitHub issue forms render sections as:
    ### Field Label

    Field Value
    """
    if not body:
        return {}

    data: Dict[str, str] = {}
    # Match ### Label followed by content up to next ### or end of text
    pattern = r"###\s+([^\n\r]+)[\r\n]+([\s\S]*?)(?=(?:[\r\n]+###|\Z))"
    matches = re.findall(pattern, body)

    for header, content in matches:
        clean_header = header.strip().lower()
        clean_value = content.strip()
        # Filter out placeholder comments or empty defaults
        if clean_value in ("_No response_", "None", "No change"):
            clean_value = ""

        if "repository url" in clean_header or "repo" in clean_header:
            data["repo_url"] = clean_value
        elif "game name" in clean_header:
            data["name"] = clean_value
        elif (
            "primary genre" in clean_header
            or "updated genre" in clean_header
            or "genre" in clean_header
        ):
            if clean_value != "Other / Let script infer":
                data["genre"] = clean_value
        elif "tech" in clean_header or "engine" in clean_header:
            data["tech"] = clean_value
        elif "description" in clean_header:
            data["description"] = clean_value

    # If repo_url was not matched via header, search for any raw git URL in body
    if not data.get("repo_url"):
        url_match = re.search(
            r"https?://(?:github\.com|gitlab\.com|codeberg\.org)/[^\s\)\>]+",
            body,
        )
        if url_match:
            data["repo_url"] = url_match.group(0).rstrip(".,;")

    return data


def parse_command_args(command_text: str) -> Dict[str, Any]:
    """Parse inline arguments from comment like '/add https://... --genre "Strategy"'."""
    tokens = command_text.strip().split()
    if not tokens:
        return {}

    action = tokens[0].lower().lstrip("/")
    result: Dict[str, Any] = {"action": action}

    if len(tokens) > 1 and not tokens[1].startswith("--"):
        result["url"] = tokens[1]

    # Simple flag parsing
    for i, token in enumerate(tokens):
        if token == "--name" and i + 1 < len(tokens):
            result["name"] = tokens[i + 1]
        elif token == "--genre" and i + 1 < len(tokens):
            result["genre"] = tokens[i + 1]
        elif token == "--tech" and i + 1 < len(tokens):
            result["tech"] = tokens[i + 1]
        elif token == "--desc" and i + 1 < len(tokens):
            result["desc"] = tokens[i + 1]

    return result


def handle_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process an issue event or issue_comment event.

    Returns dict with success status, action taken, and comment message.
    """
    comment_body = event_data.get("comment", {}).get("body", "").strip()
    issue = event_data.get("issue", {})
    issue_body = issue.get("body", "")
    issue_labels = [label["name"] for label in issue.get("labels", [])]

    action: Optional[str] = None
    url: Optional[str] = None
    name: Optional[str] = None
    genre: Optional[str] = None
    tech: Optional[str] = None
    desc: Optional[str] = None

    form_data = parse_issue_markdown_form(issue_body)

    # 1. Check comment-based slash command
    if comment_body.startswith("/"):
        cmd_info = parse_command_args(comment_body)
        action = cmd_info.get("action")
        url = cmd_info.get("url") or form_data.get("repo_url")
        name = cmd_info.get("name") or form_data.get("name")
        genre = cmd_info.get("genre") or form_data.get("genre")
        tech = cmd_info.get("tech") or form_data.get("tech")
        desc = cmd_info.get("desc") or form_data.get("description")

    # 2. Check label-based trigger
    elif "label" in event_data:
        label_name = event_data["label"]["name"]
        if label_name in ("approved-add", "add-game"):
            action = "add"
        elif label_name in ("approved-remove", "remove-game"):
            action = "remove"
        url = form_data.get("repo_url")
        name = form_data.get("name")
        genre = form_data.get("genre")
        tech = form_data.get("tech")
        desc = form_data.get("description")

    # Fallback to issue labels
    if not action:
        if "approved-add" in issue_labels:
            action = "add"
        elif "approved-remove" in issue_labels:
            action = "remove"
        url = form_data.get("repo_url")

    if not action or action not in ("add", "remove"):
        return {
            "success": False,
            "message": f"Unrecognized or unsupported IssueOps action: '{action}'.",
        }

    if not url:
        return {
            "success": False,
            "message": (
                f"Could not determine repository URL from issue or command for action '{action}'."
            ),
        }

    owner, repo, host = parse_repo_url(url)
    if not owner or not repo:
        return {
            "success": False,
            "message": f"Invalid repository URL format: `{url}`.",
        }

    if action == "add":
        add_game(url, name=name, desc=desc, tech=tech, genre=genre)
        return {
            "success": True,
            "action": "add",
            "url": url,
            "slug": f"{host}/{owner}/{repo}",
            "message": (
                f"Successfully added **{name or repo}** (`{host}/{owner}/{repo}`) to the catalog!"
            ),
        }

    elif action == "remove":
        removed = remove_game(url)
        if removed:
            return {
                "success": True,
                "action": "remove",
                "url": url,
                "slug": f"{host}/{owner}/{repo}",
                "message": f"Successfully removed **{host}/{owner}/{repo}** from the catalog.",
            }
        else:
            return {
                "success": False,
                "action": "remove",
                "url": url,
                "slug": f"{host}/{owner}/{repo}",
                "message": f"Game **{host}/{owner}/{repo}** was not found in `games.json`.",
            }

    return {"success": False, "message": "Unknown action."}


def main() -> None:
    parser = argparse.ArgumentParser(description="IssueOps event processor")
    parser.add_argument(
        "--event-path",
        default=os.getenv("GITHUB_EVENT_PATH"),
        help="Path to event JSON",
    )
    args = parser.parse_args()

    if not args.event_path or not Path(args.event_path).exists():
        print("Error: No GitHub event path provided or file does not exist.", file=sys.stderr)
        sys.exit(1)

    with open(args.event_path, "r", encoding="utf-8") as f:
        event_data = json.load(f)

    result = handle_event(event_data)
    print(json.dumps(result, indent=2))

    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
