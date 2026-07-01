from typing import Optional
from agent.schemas import (
    ParsedRequirement, ExecutionPlan, Recommendation,
    MatchScore, SearchResult, FinalResponse, DraftOutreach,
)
from agent.tools import (
    search_entities, get_entity_details, filter_by_constraints,
    calculate_match_score, get_interaction_history, draft_outreach,
)
from agent.validator import validate_recommendations
from agent.corrector import correction_loop
from agent.formatter import format_final_response


def _infer_category(objective: str) -> Optional[str]:
    obj = objective.lower()
    if any(k in obj for k in ["packaging", "container", "wrap", "box"]):
        return "packaging"
    if any(k in obj for k in ["logistics", "freight", "delivery", "shipping"]):
        return "logistics"
    if any(k in obj for k in ["textile", "fabric", "cloth"]):
        return "textiles"
    if any(k in obj for k in ["engineer", "developer", "designer", "analyst"]):
        return "professional"
    return None


def _build_why_suitable(
    entity: SearchResult,
    score: MatchScore,
    req: ParsedRequirement,
) -> str:
    parts = []
    if score.product_relevance >= 20:
        parts.append(f"strong category match ('{entity.category}')")
    if score.location_suitability == 20:
        parts.append(f"located in {entity.state}")
    if entity.certifications:
        parts.append(f"holds certifications: {', '.join(entity.certifications)}")
    if entity.capacity_units and req.hard_constraints.minimum_capacity:
        parts.append(
            f"capacity {entity.capacity_units} units ≥ required {req.hard_constraints.minimum_capacity}"
        )
    if entity.rating:
        parts.append(f"rated {entity.rating}/5 ({entity.review_count} reviews)")
    return "; ".join(parts) if parts else "Meets all specified requirements."


def run_agent(req: ParsedRequirement, plan: ExecutionPlan) -> FinalResponse:
    states = req.hard_constraints.locations or []
    category = req.preferences.category or _infer_category(req.objective)

    candidates = search_entities(
        entity_type=req.entity_type,
        category=category,
        states=states if states else None,
        limit=30,
    )

    if not candidates and states:
        candidates = search_entities(
            entity_type=req.entity_type,
            category=category,
            limit=30,
        )

    enriched: list[SearchResult] = []
    for c in candidates:
        detail = get_entity_details(c.id)
        if detail:
            enriched.append(detail)

    passing, constraint_failures = filter_by_constraints(
        enriched, req.hard_constraints
    )

    scored: list[tuple[SearchResult, MatchScore]] = []
    for entity in passing:
        score = calculate_match_score(
            entity=entity,
            req_category=category,
            req_states=states,
            preferences=req.preferences,
            constraints=req.hard_constraints,
        )
        scored.append((entity, score))

    if req.preferences.sustainable_materials:
        scored = [(e, s) for e, s in scored if e.is_sustainable]
    if req.preferences.startup_friendly:
        scored = [(e, s) for e, s in scored if e.is_startup_friendly]

    scored.sort(key=lambda x: x[1].total, reverse=True)

    top_n = scored[: req.requested_results]

    initial_recs: list[Recommendation] = []
    seen_names = set()
    for rank, (entity, score) in enumerate(top_n, start=1):
        missing_info = []
        risks = []
        if entity.contact_email is None:
            missing_info.append("No contact email on file")
        if entity.rating is None:
            missing_info.append("No rating data available")
        if entity.capacity_units is None:
            missing_info.append("Capacity not specified")
        if entity.notes:
            risks.append(f"Note: {entity.notes}")
        if entity.name in seen_names:
            risks.append("Potential duplicate record")
        seen_names.add(entity.name)

        why = _build_why_suitable(entity, score, req)

        initial_recs.append(Recommendation(
            rank=rank,
            entity=entity,
            score=score,
            why_suitable=why,
            missing_information=missing_info,
            risks=risks,
        ))

    validation_result = correction_loop(
        initial_recs=initial_recs,
        req=req,
        category=category,
        scored_pool=scored,
        max_attempts=3,
    )

    outreach_raw = draft_outreach(
        recommendations=validation_result.valid_recommendations,
        sender_context="a sustainable food-packaging startup",
        objective=req.objective,
    )
    outreach = [DraftOutreach(**o) for o in outreach_raw]

    return format_final_response(req, plan, validation_result, outreach)
