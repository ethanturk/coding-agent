"""DeepAgents-based orchestration workflow.

Replaces the previous LangGraph stub with a real DeepAgents orchestrator
that uses subagent delegation for planning, implementation, and review.
The orchestrator receives a user goal and project context, decomposes
the work via the planner subagent, delegates implementation to developer
subagents, and sends results through a reviewer subagent.

Supports LangGraph human-in-the-loop interrupts on file write operations
so that edits can be reviewed before being applied.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from deepagents import SubAgent, create_deep_agent
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.services.langgraph_checkpoint import SqliteCheckpointSaver

from app.graph.agents.developer import DEVELOPER_SUBAGENT
from app.graph.agents.planner import PLANNER_SUBAGENT
from app.graph.agents.reviewer import REVIEWER_SUBAGENT
from app.services.deepagents_fs import DockerSandbox

logger = logging.getLogger(__name__)

CHECKPOINT_DB_PATH = Path('/home/ethanturk/.openclaw/workspace/coding-agent/runtime_artifacts/langgraph_checkpoints.sqlite3')

ORCHESTRATOR_SYSTEM_PROMPT = """You are an orchestrator for a multi-model code writing and review system.
You receive a coding goal and a project workspace, then coordinate planning,
implementation, and review through specialized subagents.

## Workflow

1. **Plan** — Delegate to the `planner` subagent with the full goal.
   Include any project context (repo structure hints, test commands, etc.)
   in the task description. The planner will explore the repo and return
   a structured plan with file targets, change descriptions, and dependencies.

2. **Implement** — For each file change in the plan, delegate to a `developer`
   subagent. Include:
   - The specific file path and what to change
   - The rationale and any dependencies
   - The relevant section of the plan
   - A reminder that edits must stay within the approved plan targets
   By default, work one file at a time unless project context explicitly allows parallel developer tasks.

3. **Test** — After implementation, use `execute` to run the project's test
   command if one was provided.

4. **Review** — Delegate to the `reviewer` subagent with:
   - The original goal
   - The plan summary
   - Which files were modified
   - Test results (if any)
   The reviewer will inspect the changes and return structured feedback.

5. **Handle review feedback** — If the reviewer requests changes:
   - Re-delegate specific fixes to developer subagents
   - Re-run tests
   - Re-submit for review
   Maximum 2 review rounds, then report final state.

6. **Report** — Summarize the outcome: what was changed, test results,
   review status, and overall confidence.

## Output Format

Your final message must be a JSON object:
```json
{
  "status": "completed|needs_human_review|failed",
  "confidence": 0.9,
  "plan_summary": "Brief description of what was planned",
  "files_changed": ["path/to/file1.py", "path/to/file2.py"],
  "test_results": {"passed": true, "output": "..."},
  "review_decision": "approve|request_changes",
  "review_summary": "Brief review outcome",
  "blocking_issues": [],
  "notes": ["Any important observations"]
}
```

## Rules

- Always plan before implementing. Don't skip the planner.
- Stay within the approved target files unless project context explicitly expands scope.
- Prefer serial developer execution. Only launch parallel developer tasks when the project context explicitly says it is allowed.
- Always run tests if a test command is available.
- Always review after implementation.
- If anything fails, report clearly — don't hide errors.
- Maximum 2 review iteration rounds.
"""


def _apply_model_to_subagent(subagent: SubAgent, model: BaseChatModel) -> SubAgent:
    """Apply a model override to a subagent spec."""
    return {**subagent, "model": model}


def build_deep_agent(
    orchestrator_model: BaseChatModel,
    planner_model: BaseChatModel | None = None,
    developer_model: BaseChatModel | None = None,
    reviewer_model: BaseChatModel | None = None,
    backend: DockerSandbox | None = None,
    project_context: str = "",
    enable_hitl: bool = False,
) -> tuple[CompiledStateGraph, SqliteCheckpointSaver | None, str]:
    """Build a DeepAgents orchestrator with role-specific models.

    Args:
        orchestrator_model: LangChain model for the main orchestrator.
        planner_model: Model for planning. Defaults to orchestrator_model.
        developer_model: Model for code implementation. Defaults to orchestrator_model.
        reviewer_model: Model for code review. Defaults to orchestrator_model.
        backend: Docker sandbox backend for file operations and execution.
        project_context: Additional context about the project (test commands, etc.)
        enable_hitl: Enable human-in-the-loop interrupts on file write operations.

    Returns:
        Tuple of (compiled agent graph, checkpointer or None, thread_id).
    """
    planner = _apply_model_to_subagent(PLANNER_SUBAGENT, planner_model or orchestrator_model)
    developer = _apply_model_to_subagent(DEVELOPER_SUBAGENT, developer_model or orchestrator_model)
    reviewer = _apply_model_to_subagent(REVIEWER_SUBAGENT, reviewer_model or orchestrator_model)

    system_prompt = ORCHESTRATOR_SYSTEM_PROMPT
    if project_context:
        system_prompt += f"\n\n## Project Context\n{project_context}"

    checkpointer = None
    interrupt_on = None
    thread_id = str(uuid.uuid4())

    if enable_hitl:
        checkpointer = SqliteCheckpointSaver(str(CHECKPOINT_DB_PATH))
        interrupt_on = {
            "edit_file": True,
            "write_file": True,
        }

    agent = create_deep_agent(
        model=orchestrator_model,
        system_prompt=system_prompt,
        subagents=[planner, developer, reviewer],
        backend=backend,
        name="coding-orchestrator",
        checkpointer=checkpointer,
        interrupt_on=interrupt_on,
    )
    return agent, checkpointer, thread_id


def invoke_deep_agent(
    agent: CompiledStateGraph,
    goal: str,
    test_command: str | None = None,
    inspect_command: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Invoke the DeepAgents orchestrator with a coding goal.

    Args:
        agent: The compiled DeepAgents graph from build_deep_agent().
        goal: The user's coding goal/request.
        test_command: Optional shell command to run tests.
        inspect_command: Optional shell command to inspect the workspace.
        thread_id: Thread ID for checkpointed execution. Required if HITL is enabled.

    Returns:
        Dict with status, files_changed, confidence, review info, etc.
        If HITL is enabled and the graph is interrupted, returns status="interrupted"
        with pending_tool_calls containing the paused operations.
    """
    task_description = f"Goal: {goal}"
    if test_command:
        task_description += f"\n\nTest command: `{test_command}`"
    if inspect_command:
        task_description += f"\n\nInspect command: `{inspect_command}`"

    config = {}
    if thread_id:
        config["configurable"] = {"thread_id": thread_id}

    result = agent.invoke(
        {"messages": [{"role": "user", "content": task_description}]},
        config=config if config else None,
    )

    # Check if the graph was interrupted (HITL)
    if _is_interrupted(agent, thread_id):
        pending = _extract_pending_tool_calls(agent, thread_id)
        return {
            "status": "interrupted",
            "confidence": 0.0,
            "plan_summary": "",
            "files_changed": [],
            "test_results": None,
            "review_decision": None,
            "review_summary": "",
            "blocking_issues": [],
            "notes": ["Graph interrupted for human approval"],
            "pending_tool_calls": pending,
            "thread_id": thread_id,
        }

    return _parse_agent_result(result)


def resume_deep_agent(
    agent: CompiledStateGraph,
    thread_id: str,
    approve: bool = True,
) -> dict[str, Any]:
    """Resume a previously interrupted agent execution.

    Args:
        agent: The compiled DeepAgents graph.
        thread_id: Thread ID from the interrupted execution.
        approve: Whether to approve the pending tool calls.

    Returns:
        Dict with the final result after resumption.
    """
    config = {"configurable": {"thread_id": thread_id}}

    if approve:
        result = agent.invoke(Command(resume=True), config=config)
    else:
        result = agent.invoke(
            Command(resume="The proposed edits were rejected by the reviewer. Please stop and report the current state."),
            config=config,
        )

    if _is_interrupted(agent, thread_id):
        pending = _extract_pending_tool_calls(agent, thread_id)
        return {
            "status": "interrupted",
            "confidence": 0.0,
            "pending_tool_calls": pending,
            "thread_id": thread_id,
            **{k: [] for k in ("files_changed", "blocking_issues", "notes")},
            **{k: None for k in ("test_results", "review_decision")},
            **{k: "" for k in ("plan_summary", "review_summary")},
        }

    return _parse_agent_result(result)


def _is_interrupted(agent: CompiledStateGraph, thread_id: str | None) -> bool:
    """Check if the graph execution is in an interrupted state."""
    if not thread_id:
        return False
    try:
        state = agent.get_state({"configurable": {"thread_id": thread_id}})
        return bool(state and state.next)
    except Exception:
        return False


def _extract_pending_tool_calls(agent: CompiledStateGraph, thread_id: str) -> list[dict]:
    """Extract pending tool calls from an interrupted graph state."""
    try:
        state = agent.get_state({"configurable": {"thread_id": thread_id}})
        if not state or not state.values:
            return []
        messages = state.values.get("messages", [])
        pending = []
        for msg in reversed(messages):
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    pending.append({
                        "tool": tc.get("name", "unknown"),
                        "args": tc.get("args", {}),
                    })
                break
        return pending
    except Exception:
        return []


def _parse_agent_result(result: dict) -> dict[str, Any]:
    """Parse the final result from a DeepAgents invocation."""
    messages = result.get("messages", [])
    if not messages:
        return {
            "status": "failed",
            "confidence": 0.0,
            "plan_summary": "",
            "files_changed": [],
            "test_results": None,
            "review_decision": None,
            "review_summary": "No response from orchestrator",
            "blocking_issues": ["Orchestrator returned empty result"],
            "notes": [],
        }

    final_message = messages[-1]
    content = getattr(final_message, "content", str(final_message))
    if isinstance(content, list):
        content = " ".join(str(part) for part in content)

    # Try to parse structured JSON from the response
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return {
                "status": parsed.get("status", "completed"),
                "confidence": parsed.get("confidence", 0.5),
                "plan_summary": parsed.get("plan_summary", ""),
                "files_changed": parsed.get("files_changed", []),
                "test_results": parsed.get("test_results"),
                "review_decision": parsed.get("review_decision"),
                "review_summary": parsed.get("review_summary", ""),
                "blocking_issues": parsed.get("blocking_issues", []),
                "notes": parsed.get("notes", []),
            }
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: treat the whole response as a text summary
    return {
        "status": "completed",
        "confidence": 0.5,
        "plan_summary": content[:500] if content else "",
        "files_changed": [],
        "test_results": None,
        "review_decision": None,
        "review_summary": content[:200] if content else "",
        "blocking_issues": [],
        "notes": ["Response was not structured JSON — interpreting as text summary"],
    }
