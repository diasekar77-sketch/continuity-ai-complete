from typing import Literal
from pydantic import BaseModel, Field

CommitmentStatus = Literal["promised", "conditional", "discussed", "completed"]


class Commitment(BaseModel):
    description: str
    status: CommitmentStatus
    source_message_id: int
    quote: str


class TroubleshootingStep(BaseModel):
    step: str
    outcome: str = ""
    source_message_id: int
    quote: str


class PendingAction(BaseModel):
    description: str
    source_message_id: int
    quote: str


class CaseMemory(BaseModel):
    """Structured output of the extraction step (what the LLM must return)."""
    issue: str
    summary: str
    sentiment: str = "neutral"
    concerns: list[str] = Field(default_factory=list)
    troubleshooting: list[TroubleshootingStep] = Field(default_factory=list)
    commitments: list[Commitment] = Field(default_factory=list)
    pending_actions: list[PendingAction] = Field(default_factory=list)
    verify_before_responding: list[str] = Field(default_factory=list)


class InteractionCreate(BaseModel):
    agent_id: str
    timestamp: str | None = None


class MessageCreate(BaseModel):
    speaker: Literal["customer", "agent"]
    content: str = Field(min_length=1)
    timestamp: str | None = None


class AssistantQuery(BaseModel):
    case_id: int
    question: str = Field(min_length=3)


class LLMAnswer(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    verify_before_responding: list[str] = Field(default_factory=list)


class NewCase(BaseModel):
    customer_name: str = Field(min_length=1)
    customer_email: str | None = None
    agent_id: str
    transcript: str = Field(min_length=3)


class NewConversation(BaseModel):
    agent_id: str
    transcript: str = Field(min_length=3)


class TransferRequest(BaseModel):
    to_agent_id: str
    by: str | None = None


class StatusUpdate(BaseModel):
    status: Literal["open", "transferred", "resolved"]
    by: str | None = None


class NewAction(BaseModel):
    description: str = Field(min_length=3)
    by: str | None = None
    assigned_agent: str | None = None


class ActionStatus(BaseModel):
    done: bool
    by: str | None = None


class ChecklistUpdate(BaseModel):
    item: str = Field(min_length=1)
    checked: bool
    by: str | None = None
