from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Requirement Parsing ────────────────────────────────────────────────────────

class HardConstraints(BaseModel):
    locations: list[str] = Field(default_factory=list,
        description="States or regions required")
    certifications: list[str] = Field(default_factory=list,
        description="Required certifications e.g. food-grade, ISO-9001")
    minimum_capacity: Optional[int] = Field(None,
        description="Minimum units supplier must be able to handle")
    maximum_delivery_days: Optional[int] = Field(None,
        description="Maximum acceptable delivery lead time in days")
    availability: Optional[str] = Field(None,
        description="required availability status: available | any")
    entity_type: Optional[str] = Field(None,
        description="Required entity type: supplier | professional | business")


class Preferences(BaseModel):
    sustainable_materials: bool = False
    startup_friendly: bool = False
    min_rating: Optional[float] = None
    max_price_per_unit: Optional[float] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None


class ParsedRequirement(BaseModel):
    objective: str
    entity_type: str = Field(description="supplier | professional | business | opportunity")
    hard_constraints: HardConstraints
    preferences: Preferences
    requested_results: int = Field(default=3, ge=1, le=10)
    raw_request: str = Field(description="Original user text, sanitised")


# ── Planning ─────────────────────────────────────────────────────────────────--

class ExecutionPlan(BaseModel):
    steps: list[str]


# ── Tool Inputs / Outputs ──────────────────────────────────────────────────────

class SearchResult(BaseModel):
    id: str
    name: str
    entity_type: str
    location: Optional[str]
    state: Optional[str]
    category: Optional[str]
    certifications: list[str] = Field(default_factory=list)
    capacity_units: Optional[int]
    delivery_days: Optional[int]
    availability: str
    rating: Optional[float]
    is_sustainable: bool
    is_startup_friendly: bool
    contact_email: Optional[str]
    notes: Optional[str]
    review_count: Optional[int] = None


class MatchScore(BaseModel):
    entity_id: str
    product_relevance: float = Field(ge=0, le=30,
        description="0–30: how well category/tags match the request")
    location_suitability: float = Field(ge=0, le=20,
        description="0–20: whether entity is in required location")
    constraint_compliance: float = Field(ge=0, le=25,
        description="0–25: hard constraints satisfied")
    availability_capacity: float = Field(ge=0, le=15,
        description="0–15: availability + capacity adequacy")
    reputation: float = Field(ge=0, le=10,
        description="0–10: rating and review evidence")
    total: float = Field(ge=0, le=100)
    evidence: dict[str, str] = Field(default_factory=dict,
        description="Explanation for each dimension")


class Recommendation(BaseModel):
    rank: int
    entity: SearchResult
    score: MatchScore
    why_suitable: str
    missing_information: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


# ── Validation ─────────────────────────────────────────────────────────────────

class ValidationFailure(BaseModel):
    entity_id: str
    failure_type: str   # e.g. "hard_constraint", "missing_cert", "duplicate", "unavailable"
    detail: str


class ValidationResult(BaseModel):
    passed: bool
    failures: list[ValidationFailure] = Field(default_factory=list)
    valid_recommendations: list[Recommendation] = Field(default_factory=list)
    attempt: int = 1


# ── Final Output ───────────────────────────────────────────────────────────────

class DraftOutreach(BaseModel):
    recipient_name: str
    recipient_id: str
    subject: str
    body: str


class FinalResponse(BaseModel):
    interpreted_requirement: ParsedRequirement
    plan_followed: ExecutionPlan
    recommendations: list[Recommendation]
    draft_outreach_messages: list[DraftOutreach]
    validation_status: str   # "PASSED" | "PARTIAL" | "FAILED"
    validation_attempts: int
    validation_failures: list[ValidationFailure]
    recommended_next_action: str
    human_approval_required: bool = True
    approval_status: str = "AWAITING_APPROVAL"
    warnings: list[str] = Field(default_factory=list)
