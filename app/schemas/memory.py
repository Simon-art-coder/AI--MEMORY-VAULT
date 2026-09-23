from datetime import datetime

from pydantic import BaseModel


class SourceRead(BaseModel):
    id: str
    filename: str
    source_type: str
    raw_text_length: int
    created_at: datetime
    model_config = {"from_attributes": True}


class MemoryRead(BaseModel):
    id: str
    source_id: str
    content: str
    chunk_index: int
    extracted_facts: dict | None
    created_at: datetime
    model_config = {"from_attributes": True}


class SearchQuery(BaseModel):
    query: str


class SearchResultItem(BaseModel):
    memory_id: str
    source_filename: str
    excerpt: str
    relevance_score: float


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    using_semantic_embeddings: bool  # honest flag: real provider vs local fallback


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    answer_generated: bool  # False if degraded to raw sources (no LLM key configured)
    sources: list[SearchResultItem]


class TimelineEntry(BaseModel):
    date: datetime
    source_filename: str
    excerpt: str


class ReminderItem(BaseModel):
    kind: str  # "promise" or "task"
    description: str
    deadline: str | None
    owner: str | None
    source_filename: str
