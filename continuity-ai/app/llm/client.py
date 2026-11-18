"""LLM access. Two interchangeable extractors:
- OpenAIExtractor: real LLM, JSON output validated by Pydantic.
- HeuristicExtractor: offline rule-based fallback (tests, no-API-key demo, outage safety net).
Both return a CaseMemory; the service layer verifies it identically either way."""
import re
from pydantic import ValidationError

from app.core import config
from app.core.prompts import EXTRACTION_SYSTEM
from app.database.schemas import (
    CaseMemory, Commitment, PendingAction, TroubleshootingStep,
)


def format_transcript(messages: list[dict]) -> str:
    return "\n".join(
        f"[{m['message_id']}] {m['speaker'].upper()} ({m.get('agent_id') or 'customer'}): {m['content']}"
        for m in messages
    )


def _clean_json(text: str) -> str:
    """Strip markdown fences some providers add around JSON."""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    return t


class LLMExtractor:
    """Any OpenAI-compatible endpoint (Ollama, Groq, Gemini, GLM, OpenAI ...)."""
    name = "llm"

    def __init__(self, api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL, model=config.LLM_MODEL):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, system: str, user: str, json_mode: bool = False) -> str:
        kwargs = dict(model=self.model, temperature=0,
                      messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        if json_mode:
            try:
                r = self.client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
                return r.choices[0].message.content
            except Exception:  # some providers reject response_format; retry without it
                pass
        return self.client.chat.completions.create(**kwargs).choices[0].message.content

    def extract(self, messages: list[dict]) -> CaseMemory:
        user = "Transcript:\n" + format_transcript(messages)
        last_err = None
        for _ in range(2):  # one retry if the JSON fails validation
            raw = self.chat(EXTRACTION_SYSTEM, user, json_mode=True)
            try:
                return CaseMemory.model_validate_json(_clean_json(raw))
            except ValidationError as e:
                last_err = e
        raise RuntimeError(f"LLM returned invalid structure twice: {last_err}")


# ---------------- offline heuristic extractor ----------------
_KEY = (r"refund|replace|credit|waive|email|call back|callback|follow up|follow-up|raise|escalat|"
        r"free month|goodwill|get back to you|billing reference")
_COMPLETED = re.compile(r"\b(has been|have been|i have|i've|was)\s+(processed|refunded|issued|sent|credited|completed)\b", re.I)
_CONDITIONAL = re.compile(r"\b(if|once|provided that|subject to|as long as)\b", re.I)
_DISCUSSED = re.compile(r"\b(might|may be able|could|possibly|perhaps|looking into)\b", re.I)
_PROMISED = re.compile(r"\b(i will|i'll|we will|we'll|let me)\b", re.I)
_TROUBLE = re.compile(r"restart|clear(ed)? (the )?cache|reinstall|reset|log(ged)? out|update", re.I)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def classify(sentence: str) -> str | None:
    if not re.search(_KEY, sentence, re.I):
        return None
    if _COMPLETED.search(sentence):
        return "completed"
    if _CONDITIONAL.search(sentence):
        return "conditional"
    if _DISCUSSED.search(sentence):
        return "discussed"
    if _PROMISED.search(sentence):
        return "promised"
    return None


class HeuristicExtractor:
    name = "heuristic"

    def extract(self, messages: list[dict]) -> CaseMemory:
        commitments, steps = [], []
        for m in messages:
            for s in _sentences(m["content"]):
                if m["speaker"] == "agent":
                    status = classify(s)
                    if status:
                        commitments.append(Commitment(description=s, status=status,
                                                      source_message_id=m["message_id"], quote=s))
                    if _TROUBLE.search(s) and re.search(r"\b(please|try)\b", s, re.I):
                        steps.append(TroubleshootingStep(step=s, outcome="suggested by agent",
                                                         source_message_id=m["message_id"], quote=s))
                elif _TROUBLE.search(s) and re.search(r"\b(already|tried|did)\b", s, re.I):
                    steps.append(TroubleshootingStep(step=s, outcome="reported by customer",
                                                     source_message_id=m["message_id"], quote=s))

        cust = [m for m in messages if m["speaker"] == "customer"]
        cust_text = " ".join(m["content"] for m in cust)
        first = _sentences(cust[0]["content"])[0] if cust else "Unknown issue"
        issue = re.sub(r"^(hi|hello|hey)[,!.]?\s*", "", first, flags=re.I)
        issue = issue[:1].upper() + issue[1:]
        sentiment = "frustrated" if re.search(r"frustrat|angry|upset|second time|still haven", cust_text, re.I) else "neutral"

        concern_map = [
            (r"charged twice|double", "Duplicate charge"),
            (r"playback|stops", "Playback issue"),
            (r"refund", "Refund status unclear"),
            (r"billing reference", "Billing reference not received"),
            (r"second time|still haven|nobody told", "Repeated contact without an update"),
        ]
        concerns = [label for pat, label in concern_map if re.search(pat, cust_text, re.I)]

        pending = [PendingAction(description=c.description, source_message_id=c.source_message_id, quote=c.quote)
                   for c in commitments if c.status in ("promised", "conditional")]
        verify = []
        for c in commitments:
            if c.status == "conditional":
                verify.append(f'Verify the condition before honouring: "{c.quote}"')
            elif c.status == "promised":
                verify.append(f'Check whether this was delivered: "{c.quote}"')

        n_contacts = len({m["interaction_id"] for m in messages})

        def short(t, n=110):
            t = t.strip()
            return t if len(t) <= n else t[:n - 1].rstrip() + "..."

        parts = [f"Customer reported: {issue.rstrip('.')}. They have contacted support {n_contacts} time(s) and seem {sentiment}."]
        for status, label in (("promised", "Promised by agents"), ("conditional", "Conditional, not a promise"),
                              ("discussed", "Only discussed")):
            items = [short(c.quote) for c in commitments if c.status == status]
            if items:
                parts.append(f"{label}: " + " | ".join(items))
        tried = [short(t.step, 80) for t in steps[:3]]
        if tried:
            parts.append("Troubleshooting already tried: " + " | ".join(tried))
        summary = "\n".join(parts)
        return CaseMemory(issue=issue, summary=summary, sentiment=sentiment, concerns=concerns,
                          troubleshooting=steps, commitments=commitments, pending_actions=pending,
                          verify_before_responding=verify)


class FallbackExtractor:
    """Use the LLM; if the call or its output fails, fall back to the heuristic so the app never breaks."""

    def __init__(self, primary, fallback):
        self.primary, self.fallback, self.name = primary, fallback, primary.name

    def extract(self, messages):
        try:
            self.name = self.primary.name
            return self.primary.extract(messages)
        except Exception as e:  # noqa: BLE001 - deliberate catch-all safety net
            print(f"[ContinuityAI] LLM extraction failed ({type(e).__name__}); using offline heuristic")
            self.name = "heuristic (llm failed)"
            return self.fallback.extract(messages)


def get_llm():
    """The chat-capable LLM client, or None when no key is configured."""
    return LLMExtractor() if config.LLM_API_KEY else None


def get_extractor():
    llm = get_llm()
    return FallbackExtractor(llm, HeuristicExtractor()) if llm else HeuristicExtractor()
