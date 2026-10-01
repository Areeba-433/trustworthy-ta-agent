# Trustworthy TA Agent

**Final Year Design Project — BSEF23-18**
Bachelor of Science in Software Engineering (2023–2027)
Department of Software Engineering, Faculty of Computing & Information Technology (FCIT), University of the Punjab, Lahore

---

## Overview

**Trustworthy TA Agent** is an AI-powered educational support system that performs the core responsibilities of a teaching assistant — answering course-related queries, explaining concepts, generating and evaluating assignments/quizzes, and providing personalized learning support — while embedding a dedicated **trust and verification layer**.

Existing AI teaching assistants generate responses but often lack transparency, source verification, and reliability guarantees. This project addresses that gap by integrating Retrieval-Augmented Generation (RAG), source-backed responses, hallucination detection, confidence scoring, explainable AI, and continuous safety/fairness monitoring into a single educational platform.

## Problem Statement

LLM-based educational assistants face significant trustworthiness challenges — toxicity/safety risks, bias, robustness and security vulnerabilities, limited explainability, privacy concerns, and temporal inconsistency — that limit their adoption in high-stakes academic settings. Trustworthy TA Agent is designed to close these gaps for course-specific, institution-ready deployment.

## Core Modules

- **User Management** — authentication, role-based access (Student / Instructor / Admin)
- **Teaching Assistant Management** — create and configure multiple course-specific AI TAs
- **Course & Knowledge Base Management** — upload lecture notes, slides, PDFs; RAG indexing
- **AI Teaching Assistant** — Q&A, concept explanation, quiz/assignment generation & evaluation, personalized learning support
- **Trustworthiness Module** — RAG, source verification, hallucination detection, confidence scoring, explainability, bias/toxicity monitoring, privacy preservation
- **Academic Integrity Module** — plagiarism and suspicious-pattern detection (flagged for instructor review)
- **Teacher Dashboard** — course/material management, review AI outputs, learning analytics
- **Student Dashboard** — interact with course TA, quizzes, personal notebook, text/voice input

## Multi-Agent Architecture

| Agent | Responsibility |
|---|---|
| Teaching Assistant Management Agent | Routes requests to the correct course-specific TA |
| Retrieval Agent | Retrieves relevant content from the knowledge base via RAG |
| Teaching Assistant Agent | Generates responses, explanations, quizzes, assignments |
| Evaluation Agent | Rubric-based assignment/quiz evaluation and feedback |
| Trust Verification Agent | Source verification, hallucination detection, confidence estimation |
| Safety & Privacy Agent | Toxicity/bias detection, privacy enforcement |
| Academic Integrity Agent | Plagiarism and misconduct detection |
| Analytics Agent | Tracks frequently queried topics and learning trends |
| Feedback Agent | Collects user feedback for continuous improvement |

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React.js, HTML5, CSS3, Tailwind CSS, Recharts / Chart.js |
| Backend | FastAPI (Python), LangChain / LlamaIndex, OpenAI API or Hugging Face, LiteLLM |
| Database | PostgreSQL + ChromaDB (or MongoDB + ChromaDB) |
| Dev Tools | Visual Studio Code, Git, GitHub, Postman, Docker |

## Repository Structure

```
trustworthy-ta-agent/
├── frontend/              # React.js client
├── backend/
│   └── app/
│       ├── agents/        # Retrieval, Evaluation, Trust Verification, etc.
│       ├── models/        # DB models / schemas
│       ├── routes/        # API endpoints
│       └── main.py        # FastAPI entry point
├── docs/                  # SRS, proposal, architecture diagrams
├── .github/workflows/     # CI/CD pipelines
└── README.md
```

## Getting Started

### Prerequisites
- Node.js (v18+)
- Python (3.11+)
- PostgreSQL
- Git

### Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows PowerShell
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Backend runs at `http://localhost:8000`.

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at `http://localhost:5173` (Vite default).

### Environment Variables
Create a `.env` file in `backend/` with:
```
DATABASE_URL=postgresql://user:password@localhost:5432/trustworthy_ta
OPENAI_API_KEY=your_key_here
CHROMA_DB_PATH=./chroma_data
```

## Development Methodology

This project follows **Agile (Scrum)**, with sprints tracked on Jira. See the [Jira board](#) for the current backlog, epics, and sprint progress.

## Project Timeline

| Deliverable | Weeks | Focus |
|---|---|---|
| D1: Planning & Requirements | 1–3 | SRS, architecture, wireframes |
| D2: Core System & User Management | 4–7 | Auth, RBAC, dashboards |
| D3: TA & Course Management | 8–11 | Multi-TA, knowledge base, file upload |
| D4: AI Teaching Assistant | 12–16 | RAG pipeline, LLM integration, Q&A |
| D5: Trustworthiness & Evaluation | 17–21 | Hallucination detection, explainability, confidence scoring |
| D6: Analytics & Academic Integrity | 22–25 | Plagiarism detection, learning analytics |
| D7: Integration & Testing | 26–29 | System integration, UAT |
| D8: Deployment & Documentation | 30–32 | Final deployment, thesis, demo |

## Team

| Name | Roll Number |
|---|---|
| Areeba Mumtaz Minhas | BSEF23A025 |
| Minahil Ehsan | BSEF23A018 |
| Zuha Faiz | BSEF23M046 |
| Fareeha Azhar | BSEF23M037 |

**Supervisor:** Dr. Sanam Ahmed

## License

This project is developed as part of the Final Year Design Project at PUCIT and is intended for academic purposes.
