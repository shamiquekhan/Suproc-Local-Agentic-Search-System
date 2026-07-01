from agent.schemas import (
    ParsedRequirement, ExecutionPlan,
    ValidationResult, DraftOutreach, FinalResponse,
)


def format_final_response(
    req: ParsedRequirement,
    plan: ExecutionPlan,
    validation: ValidationResult,
    outreach: list[DraftOutreach],
) -> FinalResponse:

    rec_ids = [r.entity.id for r in validation.valid_recommendations]

    if rec_ids:
        next_action = (
            f"Send a procurement enquiry to: {', '.join(rec_ids)}. "
            f"Review draft outreach messages below before sending."
        )
    else:
        next_action = (
            "No valid matches were found. Options: (1) Expand search to adjacent states, "
            "(2) Relax constraints, (3) Add more suppliers to dataset."
        )

    warnings: list[str] = []
    if validation.attempt > 1:
        warnings.append(
            f"Validation required {validation.attempt} attempt(s) before passing."
        )
    if len(validation.valid_recommendations) < req.requested_results:
        warnings.append(
            f"Only {len(validation.valid_recommendations)} of {req.requested_results} "
            f"requested results could be validated."
        )

    status_map = {True: "PASSED", False: "FAILED"}
    status = status_map[validation.passed]
    if not validation.passed and validation.valid_recommendations:
        status = "PARTIAL"

    return FinalResponse(
        interpreted_requirement=req,
        plan_followed=plan,
        recommendations=validation.valid_recommendations,
        draft_outreach_messages=outreach,
        validation_status=status,
        validation_attempts=validation.attempt,
        validation_failures=validation.failures,
        recommended_next_action=next_action,
        human_approval_required=True,
        approval_status="AWAITING_APPROVAL",
        warnings=warnings,
    )
