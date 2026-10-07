"""Runtime configuration, read once from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    db_path: str = str(ROOT / "var" / "uds.db")
    spec_path: str = str(ROOT / "data" / "ecu_spec.json")
    chroma_dir: str = str(ROOT / "var" / "chroma")
    retrieval: str = "vector"  # "vector" (ChromaDB) or "lexical"; vector falls back to lexical on failure
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    llm_enabled: bool = True
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:3b"
    llm_timeout: float = 120.0
    cors_origins: tuple = ("http://localhost:5173",)
    max_upload_bytes: int = 1_000_000

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        return cls(
            db_path=os.getenv("DB_PATH", d.db_path),
            spec_path=os.getenv("SPEC_PATH", d.spec_path),
            chroma_dir=os.getenv("CHROMA_DIR", d.chroma_dir),
            retrieval=os.getenv("RETRIEVAL", d.retrieval).lower(),
            embedding_model=os.getenv("EMBEDDING_MODEL", d.embedding_model),
            llm_enabled=_bool("LLM_ENABLED", d.llm_enabled),
            ollama_url=os.getenv("OLLAMA_URL", d.ollama_url).rstrip("/"),
            llm_model=os.getenv("LLM_MODEL", d.llm_model),
            llm_timeout=float(os.getenv("LLM_TIMEOUT", d.llm_timeout)),
            cors_origins=tuple(o for o in os.getenv("CORS_ORIGINS", ",".join(d.cors_origins)).split(",") if o),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", d.max_upload_bytes)),
        )
