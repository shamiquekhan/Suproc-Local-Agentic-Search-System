from agent.schemas import (
    Recommendation, ParsedRequirement,
    ValidationResult, ValidationFailure,
)
from agent.tools import get_entity_details


def validate_recommendations(
    recommendations: list[Recommendation],
    req: ParsedRequirement,
    attempt: int = 1,
) -> ValidationResult:
    failures: list[ValidationFailure] = []
    valid: list[Recommendation] = []
    seen_ids: set[str] = set()

    for rec in recommendations:
        e = rec.entity
        rec_failures: list[ValidationFailure] = []

        db_entity = get_entity_details(e.id)
        if db_entity is None:
            rec_failures.append(ValidationFailure(
                entity_id=e.id,
                failure_type="not_found",
                detail=f"Entity {e.id} does not exist in the dataset.",
            ))
            failures.extend(rec_failures)
            continue

        if db_entity.entity_type != req.entity_type:
            rec_failures.append(ValidationFailure(
                entity_id=e.id,
                failure_type="wrong_entity_type",
                detail=(
                    f"Entity type '{db_entity.entity_type}' does not match "
                    f"required '{req.entity_type}'."
                ),
            ))

        if req.hard_constraints.locations:
            if db_entity.state not in req.hard_constraints.locations:
                rec_failures.append(ValidationFailure(
                    entity_id=e.id,
                    failure_type="location_constraint",
                    detail=(
                        f"Entity is in '{db_entity.state}', not in required "
                        f"{req.hard_constraints.locations}."
                    ),
                ))

        for cert in req.hard_constraints.certifications:
            if not any(cert.lower() in c.lower() for c in db_entity.certifications):
                rec_failures.append(ValidationFailure(
                    entity_id=e.id,
                    failure_type="missing_certification",
                    detail=f"Missing certification '{cert}'. Has: {db_entity.certifications}",
                ))

        if req.hard_constraints.minimum_capacity is not None:
            if db_entity.capacity_units is None:
                rec_failures.append(ValidationFailure(
                    entity_id=e.id,
                    failure_type="unknown_capacity",
                    detail=f"Capacity unknown; required ≥ {req.hard_constraints.minimum_capacity}.",
                ))
            elif db_entity.capacity_units < req.hard_constraints.minimum_capacity:
                rec_failures.append(ValidationFailure(
                    entity_id=e.id,
                    failure_type="insufficient_capacity",
                    detail=(
                        f"Capacity {db_entity.capacity_units} < required "
                        f"{req.hard_constraints.minimum_capacity}."
                    ),
                ))

        if req.hard_constraints.maximum_delivery_days is not None:
            if db_entity.delivery_days is None:
                rec_failures.append(ValidationFailure(
                    entity_id=e.id,
                    failure_type="unknown_delivery",
                    detail=f"Delivery time unknown; required ≤ {req.hard_constraints.maximum_delivery_days} days.",
                ))
            elif db_entity.delivery_days > req.hard_constraints.maximum_delivery_days:
                rec_failures.append(ValidationFailure(
                    entity_id=e.id,
                    failure_type="delivery_exceeds_limit",
                    detail=(
                        f"Delivery {db_entity.delivery_days} days > "
                        f"required ≤ {req.hard_constraints.maximum_delivery_days} days."
                    ),
                ))

        if db_entity.availability == "busy":
            rec_failures.append(ValidationFailure(
                entity_id=e.id,
                failure_type="unavailable",
                detail=f"Entity '{e.name}' is currently marked as busy/unavailable.",
            ))

        if e.id in seen_ids:
            rec_failures.append(ValidationFailure(
                entity_id=e.id,
                failure_type="duplicate",
                detail=f"Entity {e.id} appears more than once in recommendations.",
            ))
        seen_ids.add(e.id)

        if rec.score.total == 0.0:
            rec_failures.append(ValidationFailure(
                entity_id=e.id,
                failure_type="zero_score",
                detail="Match score is 0 - scoring may not have run correctly.",
            ))

        if rec_failures:
            failures.extend(rec_failures)
        else:
            valid.append(rec)

    warnings = []
    if len(valid) < req.requested_results:
        warnings.append(
            f"Only {len(valid)} valid result(s) found; {req.requested_results} were requested."
        )

    passed = len(failures) == 0

    return ValidationResult(
        passed=passed,
        failures=failures,
        valid_recommendations=valid,
        attempt=attempt,
    )
