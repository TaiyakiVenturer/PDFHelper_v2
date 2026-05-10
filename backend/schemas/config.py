from __future__ import annotations

from enum import Enum

from pydantic import BaseModel
from pydantic import Field


class LLMBackend(str, Enum):
    llama_cpp = "llama_cpp"
    openai_compat = "openai_compat"


class LlamaCppConfig(BaseModel):
    repo_id: str = "bartowski/Qwen2.5-7B-Instruct-GGUF"
    filename: str = "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    n_gpu_layers: int = -1
    n_ctx: int = 4096


class OpenAICompatConfig(BaseModel):
    base_url: str = "http://localhost:11434/v1"
    api_key: str = "sk-no-key"
    model: str = "qwen2.5:7b"


class LLMConfig(BaseModel):
    backend: LLMBackend = LLMBackend.llama_cpp
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=800, ge=100, le=8192)
    query_history_turns: int = Field(default=3, ge=1, le=20)
    llama_cpp: LlamaCppConfig = Field(default_factory=LlamaCppConfig)
    openai_compat: OpenAICompatConfig = Field(default_factory=OpenAICompatConfig)


class AppConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
