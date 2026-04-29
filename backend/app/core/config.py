import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（backend/）— 所有相对路径基于此
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# .env 文件路径
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = Field(
        default="Atelier",
        validation_alias="APP_NAME",
    )
    app_env: str = Field(default="dev", validation_alias="APP_ENV")
    app_debug: bool = Field(default=True, validation_alias="APP_DEBUG")
    database_url: str = Field(
        default=f"sqlite:///{_BACKEND_DIR / 'atelier.db'}",
        validation_alias="APP_DATABASE_URL",
    )
    log_level: str = Field(default="INFO", validation_alias="APP_LOG_LEVEL")

    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.deepseek.com", validation_alias="LLM_BASE_URL")
    llm_model: str = Field(default="deepseek-chat", validation_alias="LLM_MODEL")
    llm_reasoning_model: str = Field(default="deepseek-reasoner", validation_alias="LLM_REASONING_MODEL")

    max_history_messages: int = Field(default=20, validation_alias="MAX_HISTORY_MESSAGES")
    max_file_read_size: int = Field(default=50 * 1024, validation_alias="MAX_FILE_READ_SIZE")
    max_scan_file_size: int = Field(default=100 * 1024 * 1024, validation_alias="MAX_SCAN_FILE_SIZE")

    chunk_size: int = Field(default=500, validation_alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, validation_alias="CHUNK_OVERLAP")
    chroma_persist_dir: str = Field(
        default=str(_BACKEND_DIR / "chroma_data"),
        validation_alias="CHROMA_PERSIST_DIR",
    )

    compact_trigger: int = Field(default=10, validation_alias="COMPACT_TRIGGER")
    compact_keep_recent: int = Field(default=3, validation_alias="COMPACT_KEEP_RECENT")

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _resolve_relative_paths(self):
        """把相对 SQLite 路径和 Chroma 路径解析成基于 backend/ 的绝对路径。"""
        # SQLite: sqlite:///./xxx.db → sqlite:///absolute/path/xxx.db
        if "sqlite:///" in self.database_url and not self.database_url.startswith("sqlite:////"):
            relative = self.database_url.replace("sqlite:///", "")
            absolute = str((_BACKEND_DIR / relative).resolve())
            self.database_url = f"sqlite:///{absolute}"

        # Chroma: ./chroma_data → /absolute/path/chroma_data
        if not os.path.isabs(self.chroma_persist_dir):
            self.chroma_persist_dir = str((_BACKEND_DIR / self.chroma_persist_dir).resolve())

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
