"""Configuración validada; nunca registrar secretos."""
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    redis_url: str = 'redis://localhost:6379/0'
    api_key: SecretStr
    approval_key: SecretStr
    agent_mode: Literal['offline', 'llm'] = 'offline'
    openai_api_key: SecretStr | None = None
    openai_model: str = 'gpt-4.1-mini'
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = 'preentrega7'
    worker_concurrency: int = 5
    job_timeout: int = 180


@lru_cache
def settings():
    return Settings()
