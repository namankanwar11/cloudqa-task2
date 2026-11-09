from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class RunRequest(Strict):
    url: str = Field(min_length=8, max_length=2048)
    instruction: str = Field(min_length=8, max_length=5000)
    headless: bool = True
    secrets: dict[str, SecretStr] = Field(default_factory=dict)
    # Offline demo is explicit and is never described as AI-generated.
    mode: Literal["openai", "demo"] = "openai"

class SemanticTarget(Strict):
    role: str = Field(max_length=40)
    name: str = Field(max_length=200)
    # Optional semantic scope, e.g. dialog "Sign in". No CSS/XPath accepted.
    scope_role: str | None
    scope_name: str | None

class Assertion(Strict):
    id: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=240)
    kind: Literal["visible", "hidden", "text", "value", "checked", "url"]
    target: SemanticTarget | None
    expected: str = Field(max_length=500)

    @model_validator(mode="after")
    def valid_target(self):
        if self.kind != "url" and self.target is None:
            raise ValueError("Element assertion requires a semantic target")
        if self.kind == "checked" and self.expected not in ("true", "false"):
            raise ValueError("checked expected must be true or false")
        if self.kind == "url" and not self.expected:
            raise ValueError("URL assertion needs an expected URL")
        return self

class TestPlan(Strict):
    summary: str = Field(max_length=300)
    assertions: list[Assertion] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({a.id for a in self.assertions}) != len(self.assertions):
            raise ValueError("Assertion IDs must be unique")
        return self

class Action(Strict):
    kind: Literal["navigate", "click", "fill", "select", "check", "assert", "finish"]
    ref: str | None
    value: str | None
    assertion_id: str | None
    # The model flag is advisory. Policy also independently checks the observed control.
    destructive: bool
    reason: str = Field(max_length=240)

    @model_validator(mode="after")
    def shape(self):
        if self.kind in ("click", "fill", "select", "check") and not self.ref:
            raise ValueError("Interaction requires current observation ref")
        if self.kind in ("fill", "select", "check", "navigate") and self.value is None:
            raise ValueError("Action requires a value")
        if self.kind == "assert" and not self.assertion_id:
            raise ValueError("Assert requires an existing assertion ID")
        if self.kind == "check" and self.value not in ("true", "false"):
            raise ValueError("check value must be true or false")
        return self

class Approval(Strict):
    token: str = Field(min_length=20)
    approve: bool

class StepLog(Strict):
    number: int
    action: str
    status: str
    detail: str
    elapsed_ms: int
    screenshot: str | None = None

class Report(Strict):
    id: str
    status: Literal["QUEUED", "RUNNING", "AWAITING_APPROVAL", "PASS", "FAIL", "ERROR", "BLOCKED", "CANCELLED"]
    mode: str
    reason: str
    elapsed_ms: int = 0
    plan: dict | None = None
    assertions: dict[str, str] = Field(default_factory=dict)
    steps: list[StepLog] = Field(default_factory=list)
    approval: dict | None = None