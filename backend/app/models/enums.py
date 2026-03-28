import enum


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StepStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StepKind(str, enum.Enum):
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    REVIEW = "review"
    REPORTING = "reporting"


class AgentRole(str, enum.Enum):
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    DEVELOPER = "developer"
    TESTER = "tester"
    REVIEWER = "reviewer"
    REPORTER = "reporter"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ArtifactType(str, enum.Enum):
    LOG = "log"
    DIFF = "diff"
    FILE = "file"
    TEST_REPORT = "test_report"
    SUMMARY = "summary"


class EnvironmentStatus(str, enum.Enum):
    CREATING = "creating"
    READY = "ready"
    RUNNING = "running"
    FAILED = "failed"
    DESTROYED = "destroyed"


class PullRequestStatus(str, enum.Enum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"
