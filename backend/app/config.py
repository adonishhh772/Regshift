from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/regshift.db"
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    domain_packs_dir: Path | None = None
    demo_seed_path: Path | None = None
    erpnext_repo_path: Path | None = None
    generated_packs_dir: Path | None = None

    llm_gateway_enabled: bool = True
    llm_fallback_to_rules: bool = True
    llm_temperature: float = 0.1
    llm_request_timeout_seconds: float = 45.0
    llm_max_retries: int = 2
    llm_route_classify: str = "openai:gpt-4o-mini,azure_openai:gpt-4o-mini"
    llm_route_contract: str = "openai:gpt-4o,gateway:gpt-4o,azure_openai:gpt-4o"
    llm_route_policy_ingest: str = "openai:gpt-4o,gateway:gpt-4o,azure_openai:gpt-4o"
    llm_route_test_generation: str = "openai:gpt-4o-mini,azure_openai:gpt-4o-mini"

    openai_api_key: str | None = None
    openai_api_base: str | None = None
    llm_gateway_url: str | None = None
    llm_gateway_api_key: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    anthropic_api_key: str | None = None

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "regshift-dev-password-minimum-32-chars"
    neo4j_enabled: bool = True
    langfuse_enabled: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3001"
    langfuse_ui_url: str = "http://localhost:3001"

    def model_post_init(self, __context: object) -> None:
        import os

        env_data_dir = Path(os.environ.get("DATA_DIR", str(self.data_dir)))
        self.data_dir = env_data_dir
        self.domain_packs_dir = self.data_dir / "domain_packs"
        self.demo_seed_path = self.data_dir / "demo_seed" / "erpnext_index.json"
        self.erpnext_repo_path = self.data_dir / "repos" / "erpnext"
        self.generated_packs_dir = self.data_dir / "generated_packs"
        self.neo4j_uri = os.environ.get("NEO4J_URI", self.neo4j_uri)
        self.neo4j_user = os.environ.get("NEO4J_USER", self.neo4j_user)
        self.neo4j_password = os.environ.get("NEO4J_PASSWORD", self.neo4j_password)
        self.neo4j_enabled = os.environ.get("NEO4J_ENABLED", "true").lower() == "true"
        self.langfuse_enabled = os.environ.get("LANGFUSE_ENABLED", "false").lower() == "true"
        self.langfuse_public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", self.langfuse_public_key)
        self.langfuse_secret_key = os.environ.get("LANGFUSE_SECRET_KEY", self.langfuse_secret_key)
        self.langfuse_host = os.environ.get("LANGFUSE_HOST", self.langfuse_host)
        self.langfuse_ui_url = os.environ.get("LANGFUSE_UI_URL", self.langfuse_ui_url)
        self.llm_gateway_enabled = os.environ.get("LLM_GATEWAY_ENABLED", str(self.llm_gateway_enabled)).lower() == "true"
        self.llm_fallback_to_rules = os.environ.get(
            "LLM_FALLBACK_TO_RULES",
            str(self.llm_fallback_to_rules),
        ).lower() == "true"
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", self.openai_api_key)
        self.openai_api_base = os.environ.get("OPENAI_API_BASE", self.openai_api_base)
        self.llm_gateway_url = os.environ.get("LLM_GATEWAY_URL", self.llm_gateway_url)
        self.llm_gateway_api_key = os.environ.get("LLM_GATEWAY_API_KEY", self.llm_gateway_api_key)
        if self.llm_gateway_api_key is None and self.llm_gateway_url:
            self.llm_gateway_api_key = self.openai_api_key
        self.azure_openai_api_key = os.environ.get("AZURE_OPENAI_API_KEY", self.azure_openai_api_key)
        self.azure_openai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", self.azure_openai_endpoint)
        self.azure_openai_api_version = os.environ.get(
            "AZURE_OPENAI_API_VERSION",
            self.azure_openai_api_version,
        )
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", self.anthropic_api_key)
        self.llm_route_classify = os.environ.get("LLM_ROUTE_CLASSIFY", self.llm_route_classify)
        self.llm_route_contract = os.environ.get("LLM_ROUTE_CONTRACT", self.llm_route_contract)
        self.llm_route_policy_ingest = os.environ.get("LLM_ROUTE_POLICY_INGEST", self.llm_route_policy_ingest)
        self.llm_route_test_generation = os.environ.get(
            "LLM_ROUTE_TEST_GENERATION",
            self.llm_route_test_generation,
        )


settings = Settings()
