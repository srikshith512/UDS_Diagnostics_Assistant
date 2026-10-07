"""Application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import router
from .config import Settings
from .db import Database
from .rag.llm import DisabledLlm, OllamaClient
from .rag.retriever import Chunk, build_retriever
from .uds.spec import load_spec

log = logging.getLogger("uds")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        app.state.settings = settings
        app.state.spec = spec = load_spec(settings.spec_path)
        app.state.db = db = Database(settings.db_path)
        app.state.retriever = retriever = build_retriever(settings.retrieval, settings.chroma_dir, settings.embedding_model)
        app.state.llm = OllamaClient(settings.ollama_url, settings.llm_model, settings.llm_timeout) if settings.llm_enabled else DisabledLlm()
        retriever.add([Chunk(s["id"], s["title"], s["text"]) for s in spec.sections])
        retriever.add([Chunk(d["chunk_id"], d["title"], d["text"], d["name"]) for d in db.list_documents()])
        log.info("Ready: retrieval=%s llm=%s", retriever.mode, app.state.llm.model)
        yield

    app = FastAPI(title="UDS Diagnostics Assistant", version="1.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse({"detail": "Internal server error. Check the server log."}, status_code=500)

    return app


app = create_app()
