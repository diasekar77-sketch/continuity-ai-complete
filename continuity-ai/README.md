# ContinuityAI
AI-powered customer conversation memory and handover assistant (RAG + LLM).

When a support case changes hands, ContinuityAI preserves what was said, tracks what was promised
(promised / conditional / discussed / completed), retrieves the company policy that applies, and gives
the incoming agent a grounded briefing. It supports the agent's decision; it never commits on the company's behalf.

## Run it (two terminals)
```bash
pip install -r requirements.txt
cp .env.example .env              # optional: fill in LLM_API_KEY / LLM_BASE_URL / LLM_MODEL

# terminal 1: backend (auto-loads the sample case + sample policies on first start)
python run.py                     # API docs: http://127.0.0.1:8000/docs

# terminal 2: frontend
streamlit run frontend/Home.py    # opens http://localhost:8501
```
No API key? It still works in "offline evidence mode" (rule-based extraction, evidence-only answers).
First start with sentence-transformers downloads a small embedding model; if that is impossible the app
falls back to a built-in hashing embedder automatically.

## Architecture
- **SQLite** = source of truth (transcripts, cases, commitments, actions). Re-analysis never touches transcripts.
- **ChromaDB** = searchable copies: policy sections and transcript messages (filtered by case_id).
- **Pipeline A (conversation RAG):** question -> case-scoped message retrieval + neighbouring turns + tracked commitments.
- **Pipeline B (policy RAG):** section-aware chunks -> local embeddings -> retrieval with an abstain threshold.
- The assistant receives conversation, commitments and policy as separate labelled evidence groups, and its
  citations are validated against the evidence actually supplied.
- **Quote verification:** every extracted commitment must quote the transcript verbatim; fabricated quotes are flagged,
  wrong message ids are re-anchored, customer statements can never become commitments.
- `evidence coverage` = share of extracted items whose quotes were verified (not an LLM self-reported confidence).
- If the LLM fails, extraction and answers fall back to the offline mode instead of erroring.

## Layout
```
app/        FastAPI backend (api, services, rag, llm, database)
frontend/   Streamlit UI (Home = dashboard, pages/ = case workspace, knowledge base)
data/       sample_conversations/ and sample_policies/ (the policies are fictional)
tests/      22 tests: extraction, verification, policy RAG, assistant, API
```
Run tests: `python -m pytest -q`

## Endpoints
`GET /cases`, `GET /cases/{id}`, `GET /cases/{id}/history`, `POST /cases/{id}/process`, `GET /cases/{id}/handover`,
`POST /cases/{id}/interactions`, `POST /interactions/{id}/messages`, `POST /documents/upload`, `GET /documents`,
`GET /documents/search`, `POST /assistant/query`

## Limitations (MVP)
No authentication, no live channel integration, single-tenant, small-document scale, fictional sample policies.

## Adding and tracking cases
- **New Case** page: paste a transcript (`Customer:` / `Agent:` lines) to create a case, or add a conversation to an existing case.
- Dashboard: search by customer or issue, filter by status, newest activity first.
- Case Workspace: Transcript tab keeps every past conversation; "Case actions" marks resolved or transfers to another agent.
- After new conversations are added, the workspace shows a "re-run analysis" warning.
- API: `POST /cases`, `POST /cases/{id}/conversations`, `POST /cases/{id}/transfer`, `POST /cases/{id}/status`, `GET /agents`.

## Record Call (live speech to text)
The **Record Call** page transcribes a call as it happens using the browser's built-in speech recognition
(Google Chrome or Microsoft Edge, microphone permission and an internet connection required; no extra install or API key).
Tap **Customer speaking** / **Agent speaking** (or press Space) to label who is talking, review and fix the transcript,
then save it as a new case or as a new conversation on an existing case. The summary for the next agent is generated on save.
Limits: speakers are labelled by you, not detected automatically; rule-based extraction (offline mode) is English-only.

## Actions, checklist and activity (follow-up tracking)
- Every promised/conditional agent statement becomes a follow-up **action** with its source quote. Agents tick actions
  done (saved with who and when), reopen them, or add their own. Done and manual actions survive re-analysis; pending AI
  actions are rebuilt from the transcript. Statements are matched by a hash of their wording.
- The "Verify before responding" checklist ticks are saved per case.
- **Activity** tab: a timeline of case creation, conversations, analyses, action changes, transfers and status changes,
  each attributed to the agent chosen under "Working as" in the sidebar.
- Dashboard: "Need follow-up" counts unresolved cases with open actions and falls as actions are completed;
  "Assigned to me" follows the selected agent.
- API: `GET/POST /cases/{id}/actions`, `POST /actions/{id}/status`, `POST /cases/{id}/checklist`, `GET /cases/{id}/events`.
- Older databases are migrated automatically on startup.
