from agent.schemas import ParsedRequirement, ExecutionPlan

def build_plan(req: ParsedRequirement) -> ExecutionPlan:
    steps = [
        f"Search {req.entity_type} records by category and location",
        "Retrieve full details for each candidate",
        "Filter candidates that fail hard constraints",
        "Score remaining candidates using transparent 5-dimension scoring",
        "Rank candidates and select top results",
        "Validate every recommendation against dataset",
        "Correct and retry if validation fails (max 3 attempts)",
        "Draft outreach messages for approved candidates",
        "Prepare final response — awaiting human approval",
    ]
    if req.preferences.sustainable_materials:
        steps.insert(2, "Apply sustainability preference filter")
    if req.hard_constraints.certifications:
        steps.insert(2, f"Verify certifications: {req.hard_constraints.certifications}")
    return ExecutionPlan(steps=steps)
