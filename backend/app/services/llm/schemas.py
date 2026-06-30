from typing import Any

from pydantic import BaseModel, Field, field_validator


class ModelRoute(BaseModel):
    provider: str
    model: str


class LlmInvocationMeta(BaseModel):
    task: str
    provider: str
    model: str
    route_index: int = 0
    latency_ms: int | None = None
    used_fallback_rules: bool = False


class ClassifyAlternative(BaseModel):
    domain: str
    score: float = Field(ge=0.0, le=1.0)


class LlmClassifyResult(BaseModel):
    domain: str
    confidence: float = Field(ge=0.0, le=1.0)
    alternatives: list[ClassifyAlternative] = Field(default_factory=list)
    reasoning: str | None = None


class LlmContractExtraction(BaseModel):
    entity: str
    threshold_amount: int | None = None
    obligations: list[str] = Field(default_factory=list)
    approval_roles: list[str] = Field(default_factory=list)
    reasoning: str | None = None

    @field_validator("obligations", "approval_roles", mode="before")
    @classmethod
    def strip_obligations(cls, value: Any) -> list[str]:
        if not value:
            return []
        return [str(item).strip() for item in value if str(item).strip()]


class LlmPolicyRule(BaseModel):
    id: str
    type: str
    value: str | int | bool | None = None
    key: str | None = None
    citation: str
    description: str


class LlmPolicyExtraction(BaseModel):
    domain: str
    obligations: list[str] = Field(default_factory=list)
    threshold: int | None = None
    approval_roles: list[str] = Field(default_factory=list)
    agent_limits: dict[str, bool] = Field(default_factory=dict)
    rules: list[LlmPolicyRule] = Field(default_factory=list)
    reasoning: str | None = None


class LlmGeneratedTestItem(BaseModel):
    id: str
    name: str
    description: str
    contract_rule: str
    assertions: list[str] = Field(default_factory=list)
    pytest_code: str = ""

    @field_validator("assertions", mode="before")
    @classmethod
    def strip_assertions(cls, value: Any) -> list[str]:
        if not value:
            return []
        return [str(item).strip() for item in value if str(item).strip()]


class LlmTestGenerationResult(BaseModel):
    tests: list[LlmGeneratedTestItem] = Field(default_factory=list)
    reasoning: str | None = None


class LlmGatewayStatus(BaseModel):
    enabled: bool
    fallback_to_rules: bool
    routes: dict[str, list[ModelRoute]]
    providers_configured: dict[str, bool]
    default_temperature: float
    request_timeout_seconds: float
