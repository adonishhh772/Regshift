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
    openai_api_key: str | None = None
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


settings = Settings()
