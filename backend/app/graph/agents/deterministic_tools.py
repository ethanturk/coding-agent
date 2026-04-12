"""Deterministic edit pipeline exposed as LangChain tools.

These tools wrap the existing deterministic edit proposal system (semantic
patches, region targeting, edit intent classification) so that DeepAgents
developer subagents can use them as a fast/cheap fallback before resorting
to full agentic code generation.

The developer subagent can:
1. Call `propose_edit` to get a deterministic edit suggestion
2. Review the suggestion and either apply it directly or use it as a
   starting point for a more nuanced edit
"""

from __future__ import annotations

import json

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.services.developer_agent import (
    build_edit_proposal,
    build_search_context,
    classify_change_type,
    detect_language_family,
    infer_edit_intent,
    infer_targets_from_repo,
    search_terms_from_goal,
)


class ProposeEditInput(BaseModel):
    """Input for the propose_edit tool."""

    goal: str = Field(description="The user's goal/request for this edit")
    file_path: str = Field(description="Path to the file to edit")
    current_content: str = Field(description="Current content of the file")


class InferTargetsInput(BaseModel):
    """Input for the infer_targets tool."""

    goal: str = Field(description="The user's goal/request")
    file_list: str = Field(
        description="Newline-separated list of file paths in the repository"
    )


class AnalyzeFileInput(BaseModel):
    """Input for the analyze_file tool."""

    goal: str = Field(description="The user's goal/request")
    file_path: str = Field(description="Path to the file to analyze")


def _propose_edit(goal: str, file_path: str, current_content: str) -> str:
    """Generate a deterministic edit proposal using semantic patches.

    Returns a JSON object with the proposed edit including:
    - intent: the type of edit (replace_block, insert_import_like, etc.)
    - target_region: which part of the file to modify
    - old_text/new_text: the before/after content
    - validation: whether the proposal passes validation checks
    - confidence indicators
    """
    proposal = build_edit_proposal(goal, file_path, current_content)
    # Return a concise summary
    return json.dumps(
        {
            "path": proposal.get("path"),
            "intent": proposal.get("intent"),
            "change_type": proposal.get("change_type"),
            "changed": proposal.get("changed", False),
            "reason": proposal.get("reason"),
            "target_region": proposal.get("target_region"),
            "validation": proposal.get("validation"),
            "diff_preview": proposal.get("diff_preview", "")[:500],
            "new_text": proposal.get("new_text", "")[:2000],
        },
        indent=2,
    )


def _infer_targets(goal: str, file_list: str) -> str:
    """Infer which files should be modified based on the goal.

    Uses heuristic scoring (keyword matching, path analysis, companion
    file detection) to rank files by relevance to the goal.
    """
    files = [f.strip() for f in file_list.strip().splitlines() if f.strip()]
    targets = infer_targets_from_repo(goal, files)
    search_terms = search_terms_from_goal(goal)
    return json.dumps(
        {
            "targets": targets[:12],
            "search_terms": search_terms,
            "total_files_analyzed": len(files),
        },
        indent=2,
    )


def _analyze_file(goal: str, file_path: str) -> str:
    """Analyze a file's role relative to the goal.

    Returns the detected language family, change type classification,
    and inferred edit intent without actually generating an edit.
    """
    return json.dumps(
        {
            "file_path": file_path,
            "language_family": detect_language_family(file_path),
            "change_type": classify_change_type(file_path),
            "edit_intent": infer_edit_intent(goal, file_path),
        },
        indent=2,
    )


propose_edit_tool = StructuredTool.from_function(
    name="propose_edit",
    func=_propose_edit,
    description=(
        "Generate a deterministic edit proposal for a file using semantic patch analysis. "
        "Use this as a fast starting point before writing your own edit. Returns a JSON "
        "object with the proposed changes, target region, and validation status. "
        "If the proposal looks good, you can apply it directly with edit_file. "
        "If not, use it as context to write a better edit."
    ),
    args_schema=ProposeEditInput,
)

infer_targets_tool = StructuredTool.from_function(
    name="infer_targets",
    func=_infer_targets,
    description=(
        "Analyze a list of repository files and rank them by relevance to the goal. "
        "Uses heuristic scoring (keyword matching, path patterns, companion file detection) "
        "to identify which files likely need modification. Returns ranked targets and "
        "extracted search terms."
    ),
    args_schema=InferTargetsInput,
)

analyze_file_tool = StructuredTool.from_function(
    name="analyze_file",
    func=_analyze_file,
    description=(
        "Quickly classify a file's language family, change type, and likely edit intent "
        "relative to the goal. Use this to understand what kind of change is needed "
        "before reading the full file."
    ),
    args_schema=AnalyzeFileInput,
)

DETERMINISTIC_TOOLS = [propose_edit_tool, infer_targets_tool, analyze_file_tool]
"""All deterministic pipeline tools available to developer subagents."""
