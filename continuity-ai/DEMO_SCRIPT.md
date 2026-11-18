# Demo script (about 4 minutes)

**Before recording:** both terminals running, browser at the dashboard, LLM key set in `.env` (or say you are in offline mode).
Do one dry run first so the model is warm.

## 1. The problem (20 s)
"When a support case moves between agents, the new agent often can't tell what was promised and what was only
discussed. The customer repeats themselves, and the company risks contradicting itself or honouring something
that was never a promise. ContinuityAI fixes the handover."

## 2. Dashboard (20 s)
Show the case table and the "Need follow-up" count. Open Aarav Menon's case (duplicate subscription charge, transferred to Meera).

## 3. Transcript is the source of truth (25 s)
Transcript tab: two interactions, two agents. "The original conversation is stored exactly. The AI summary never replaces it."

## 4. AI analysis (40 s)
Click **Analyse case with AI**. Show the summary, concerns, and the commitments:
- refund = **conditional** ("if billing confirms..."), not promised
- billing reference email = **promised** (and overdue, the customer says they never got it)
- free month = **discussed**
Point at "verified" and the evidence coverage bar: "every item must quote the transcript; fabricated quotes get flagged."

## 5. Policy grounding (30 s)
Scroll to Applicable company policy: duplicate-charge rule (no approval before billing verification) and the goodwill
rule (senior agents only, manager approval). "The recommendation comes from the company's documents, not the model's general knowledge."

## 6. Ask the assistant (60 s)
Click **Was a refund actually promised?** -> answer says only conditional; open Evidence to show the exact quote.
Click **Can I offer a free month?** -> policy says senior agent plus manager approval.
Type an unrelated policy question (e.g. "hardware warranty replacement") -> "not found in the uploaded policies". "It refuses to guess."

## 7. Knowledge Base (20 s)
Show upload and policy search. Optionally upload a PDF live.

## 8. Close (20 s)
"Stack: FastAPI, Streamlit, SQLite plus ChromaDB, local embeddings, an OpenAI-compatible LLM. Design choices: transcript as source of
truth, verified quotes, abstain on weak retrieval, human decides."

## Likely questions
- *Hallucination?* Quote verification, validated citations, abstain threshold, offline fallback.
- *Why two stores?* SQLite for reliable records; Chroma only for semantic search over copies.
- *Next steps?* Auth, ticketing integration (Zendesk/Freshdesk), streaming new messages, evaluation set for extraction accuracy.
