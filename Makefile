.PHONY: install test dev-backend dev-frontend up down pull-model

install:
	cd backend && pip install -r requirements-dev.txt && cd ../frontend && npm install
test:
	cd backend && python -m pytest -q
dev-backend:
	cd backend && RETRIEVAL=lexical uvicorn app.main:app --reload --port 8000
dev-frontend:
	cd frontend && npm run dev
up:
	cp -n .env.example .env || true
	docker compose up --build -d
down:
	docker compose down
pull-model:
	docker compose exec ollama ollama pull $${LLM_MODEL:-qwen2.5:3b}
