# AI Code Assistant (Improved)

This repository contains an improved version of the AI code assistant:

- **backend/** – Django 5 + DRF + RAG (FAISS + SentenceTransformers) + Ollama integration with multi-source retrieval.
- **frontend/** – Angular standalone chat UI consuming `/api/code-qa/` and managing multiple RAG sources.
- **docker-compose.yml** – Postgres + Ollama + backend.

The UI now exposes a RAG Source Manager to create, éditer, or rebuild individual sources directly from the chat screen.

See `backend/README.md` and `frontend/README.md` for more details on the new multi-source RAG workflow, APIs, and UI.
