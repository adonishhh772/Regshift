from enum import StrEnum
from typing import Final

LLM_ROUTE_SEPARATOR: Final[str] = ":"
LLM_ROUTE_CHAIN_SEPARATOR: Final[str] = ","

CONFIDENCE_DETERMINISTIC: Final[str] = "deterministic"
CONFIDENCE_POLICY_SOURCED: Final[str] = "policy_sourced"
CONFIDENCE_LLM: Final[str] = "llm"
CONFIDENCE_HYBRID: Final[str] = "hybrid"


class LlmProviderName(StrEnum):
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    GATEWAY = "gateway"


class LlmTaskName(StrEnum):
    CLASSIFY = "classify"
    CONTRACT_COMPILE = "contract_compile"
    POLICY_INGEST = "policy_ingest"
    TEST_GENERATION = "test_generation"
