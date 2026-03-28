from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class WorkflowState(TypedDict, total=False):
    run_id: str
    goal: str
    status: str
    plan: dict
    implementation: dict
    tests: dict
    review: dict


def planner_node(state: WorkflowState) -> WorkflowState:
    goal = state["goal"]
    return {
        **state,
        "status": "planned",
        "plan": {
            "summary": f"Plan for: {goal}",
            "steps": [
                "Inspect repository and constraints",
                "Implement requested changes",
                "Run validation tests",
                "Review outcome",
            ],
        },
    }


def developer_node(state: WorkflowState) -> WorkflowState:
    plan = state.get("plan", {})
    return {
        **state,
        "status": "implemented",
        "implementation": {
            "summary": "Developer completed MVP implementation stub",
            "based_on": plan,
            "changed_files": ["app/main.py", "app/services/executor.py"],
        },
    }


def tester_node(state: WorkflowState) -> WorkflowState:
    return {
        **state,
        "status": "tested",
        "tests": {
            "passed": True,
            "summary": "Stub validation checks passed",
        },
    }


def reviewer_node(state: WorkflowState) -> WorkflowState:
    return {
        **state,
        "review": {
            "approved": True,
            "notes": "MVP multi-step workflow completed",
        },
        "status": "completed",
    }


def build_graph():
    graph = StateGraph(WorkflowState)
    graph.add_node("planner", planner_node)
    graph.add_node("developer", developer_node)
    graph.add_node("tester", tester_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "developer")
    graph.add_edge("developer", "tester")
    graph.add_edge("tester", "reviewer")
    graph.add_edge("reviewer", END)
    return graph.compile()
