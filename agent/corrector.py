from agent.schemas import (
    ParsedRequirement, Recommendation,
    ValidationResult,
)
from agent.validator import validate_recommendations

MAX_ATTEMPTS = 3


def correction_loop(
    initial_recs: list[Recommendation],
    req: ParsedRequirement,
    category: str,
    scored_pool: list[tuple],  # all scored candidates
    max_attempts: int = MAX_ATTEMPTS,
) -> ValidationResult:
    current_recs = initial_recs
    failed_ids: set[str] = set()

    for attempt in range(1, max_attempts + 1):
        result = validate_recommendations(current_recs, req, attempt=attempt)

        if result.passed:
            return result

        for f in result.failures:
            failed_ids.add(f.entity_id)

        still_valid = result.valid_recommendations

        needed = req.requested_results - len(still_valid)
        already_included = {r.entity.id for r in still_valid}
        replacements = []

        for entity, score in scored_pool:
            if entity.id in failed_ids or entity.id in already_included:
                continue
            if len(replacements) >= needed:
                break
            replacements.append(Recommendation(
                rank=len(still_valid) + len(replacements) + 1,
                entity=entity,
                score=score,
                why_suitable=f"Replacement candidate after validation failure (attempt {attempt})",
                missing_information=[],
                risks=[],
            ))

        current_recs = still_valid + replacements

        if not current_recs:
            break

    final = validate_recommendations(current_recs, req, attempt=max_attempts)
    return final
