from pydantic import BaseModel


class DiffStats(BaseModel):
    additions: int = 0
    deletions: int = 0


class FileActionValidation(BaseModel):
    touched_by_test: bool = False
    touched_by_build: bool = False
    touched_by_lint: bool = False


class RunFileAction(BaseModel):
    path: str
    action: str
    phase: str
    status: str
    intent: str
    rationale: str | None = None
    confidence: str | None = None
    source: str | None = None
    diff_stats: DiffStats | None = None
    validation: FileActionValidation | None = None


class ValidationCheckSummary(BaseModel):
    state: str
    summary: str | None = None


class RunValidationSummary(BaseModel):
    test: ValidationCheckSummary
    build: ValidationCheckSummary
    lint: ValidationCheckSummary


class RunPrState(BaseModel):
    branch_name: str | None = None
    branch_url: str | None = None
    base_branch: str | None = None
    head_sha: str | None = None
    pr_number: int | None = None
    pr_title: str | None = None
    pr_url: str | None = None
    status: str
    review_state: str | None = None
    mergeable: bool | None = None
    merge_commit_sha: str | None = None
    provider: str | None = None


class PlannedActionCounts(BaseModel):
    create: int = 0
    modify: int = 0
    delete: int = 0
    rename: int = 0
    review_only: int = 0


class PlannedActionSummary(BaseModel):
    total_files: int
    counts: PlannedActionCounts
    highlights: list[str] = []


class RunValidationStateSummary(BaseModel):
    test: str
    build: str
    lint: str


class RunPrStateSummary(BaseModel):
    status: str
    pr_number: int | None = None
    pr_url: str | None = None
    review_state: str | None = None


class RunOperatorSummary(BaseModel):
    stage: str
    file_actions: list[RunFileAction]
    validation: RunValidationSummary
    pr: RunPrState


class RunListOperatorSummary(BaseModel):
    stage: str
    planned_action_summary: PlannedActionSummary
    validation_summary: RunValidationStateSummary
    pr_summary: RunPrStateSummary
