# JobUndo — AI-Powered Job Application Agent

> **Status: Phase 1 — Foundation**

An autonomous AI agent that turns your resume and a job description into a complete, tailored application package: customised resume, personalised cover letter, and cold outreach emails.

---

## Architecture

```
                         USER
                           │
                           ▼
                  ┌─────────────────┐
                  │  CHAT FRONTEND  │
                  │  HTML/CSS/JS    │
                  └────────┬────────┘
                           │ HTTP
                           ▼
                  ┌─────────────────┐
                  │     NGINX       │
                  │  Reverse Proxy  │
                  └──┬──────────┬───┘
                     │          │
               /api/ │          │ /agent/
                     ▼          ▼
            ┌──────────┐  ┌──────────┐
            │  DJANGO  │  │ FASTAPI  │
            │ Auth/CRUD│  │ Agent API│
            └────┬─────┘  └────┬─────┘
                 │              │
                 └──────┬───────┘
                        │
                        ▼
               ┌─────────────────┐
               │    LANGGRAPH    │
               │  Agent Workflow │
               └────────┬────────┘
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
        OLLAMA      POSTGRES      TOOLS
                    + pgvector
```

## Services

| Service | Port | Responsibility |
|---------|------|----------------|
| `nginx` | 80 | Reverse proxy, static files |
| `django` | 8000 | Auth, user accounts, CRUD, resume upload |
| `fastapi` | 8001 | Agent API, SSE streaming, LangGraph execution |
| `postgres` | 5432 | Persistent data + pgvector for embeddings |
| `ollama` | 11434 | Local LLM inference + embeddings |

## Agent Pipeline

```
parse_jd → parse_resume → skill_gap_analysis → company_research
→ resume_rewriter → cover_letter_generator → cold_email_drafter
→ quality_checker → (retry?) → package_store
```

---

## Quick Start

### 1. Prerequisites

- Docker Desktop with WSL2 (Windows)
- NVIDIA GPU drivers + Container Toolkit (optional, for GPU acceleration)
- Git

### 2. Setup

```bash
git clone <repo-url>
cd JobUndo

# Copy environment template
cp .env.example .env
# Edit .env with your values (especially secrets)

# Start all services
docker compose up --build
```

### 3. Pull the AI model

```bash
# After containers are running:
docker exec jobundo_ollama ollama pull llama3.2:3b
docker exec jobundo_ollama ollama pull nomic-embed-text
```

### 4. Create superuser

```bash
docker exec -it jobundo_django python manage.py createsuperuser
```

### 5. Access

| URL | Description |
|-----|-------------|
| http://localhost | Frontend |
| http://localhost:8000/admin | Django admin |
| http://localhost:8000/api/health/ | Django health check |
| http://localhost:8001/health | FastAPI health check |
| http://localhost:8001/docs | FastAPI Swagger docs |

---

## Project Structure

```
JobUndo/
├── frontend/               # HTML/CSS/JS — chatbot interface
│   ├── index.html
│   ├── css/main.css
│   └── js/main.js
│
├── backend/                # Django — auth, CRUD, uploads
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── manage.py
│   ├── config/             # Django project config
│   └── apps/
│       ├── accounts/       # Custom user model, auth
│       ├── resumes/        # Resume upload + storage
│       └── applications/   # Application tracking
│
├── agent/                  # FastAPI + LangGraph
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py             # FastAPI app
│   ├── config.py           # Pydantic settings
│   ├── state.py            # AgentState TypedDict
│   ├── graph.py            # LangGraph workflow
│   ├── nodes/              # One node per agent step
│   ├── tools/              # Agent tools
│   └── db/                 # Async database session
│
├── infra/
│   ├── nginx/nginx.conf
│   └── postgres/init.sql
│
├── tests/
│   ├── backend/
│   └── agent/
│
├── docker-compose.yml
├── .env.example
└── .gitignore
```

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ | Foundation — Docker, Django, FastAPI, DB |
| 2 | 🔜 | Resume + JD parsing |
| 3 | 🔜 | LangGraph agent workflow |
| 4 | 🔜 | Skill gap analysis |
| 5 | 🔜 | RAG + company research |
| 6 | 🔜 | Resume tailoring |
| 7 | 🔜 | Cover letters + outreach emails |
| 8 | 🔜 | Quality evaluation + retry loop |
| 9 | 🔜 | PDF generation |
| 10 | 🔜 | SSE streaming + polished UI |
| 11 | 🔜 | Testing + observability |
| 12 | 🔜 | Deployment |
| 13 | 🔜 | Advanced agentic features |

---

## Technology Stack

- **Frontend**: HTML, Vanilla CSS, Vanilla JavaScript
- **Backend**: Django 4.2 + Django REST Framework
- **Agent API**: FastAPI
- **Agent Orchestration**: LangGraph
- **LLM + Embeddings**: Ollama (local, model configurable via env)
- **Database**: PostgreSQL 16
- **Vector Search**: pgvector
- **AI Framework**: LangChain (where it adds value)
- **PDF Parsing**: pdfplumber
- **PDF Generation**: ReportLab
- **Infrastructure**: Docker + docker-compose
