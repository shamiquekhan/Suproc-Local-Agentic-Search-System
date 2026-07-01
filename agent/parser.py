import re
from typing import Optional
from agent.schemas import ParsedRequirement, HardConstraints, Preferences
from agent.prompts import PARSE_SYSTEM_PROMPT

# Preferred model; users may override by environment or CLI later
MODEL = "qwen3:4b"


def _sanitise_input(text: str) -> str:
    blocked = [
        "ignore previous", "system prompt", "jailbreak",
        "override", "act as", "forget instructions",
    ]
    clean = text
    for b in blocked:
        clean = re.sub(b, "[REDACTED]", clean, flags=re.IGNORECASE)
    return clean[:2000]


def parse_requirement(user_request: str) -> ParsedRequirement:
    """
    Try to use Ollama's `chat` for structured JSON output. If Ollama is not
    available or the call fails, fall back to the local heuristic parser.
    """
    safe_input = _sanitise_input(user_request)

    try:
        # Lazy import so tests run without Ollama installed
        from ollama import chat

        schema = ParsedRequirement.model_json_schema()
        response = chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                {"role": "user", "content": safe_input},
            ],
            format=schema,
            options={"temperature": 0.1, "num_ctx": 4096},
        )

        # `response.message.content` contains the model output as a string
        raw = getattr(response, "message", None)
        if raw:
            raw_text = raw.content
        else:
            raw_text = str(response)

        parsed = ParsedRequirement.model_validate_json(raw_text)
        parsed.raw_request = safe_input
        return parsed

    except Exception:
        # Fallback deterministic parser
        safe = safe_input
        locations = []
        if "south india" in safe.lower():
            locations = ["Karnataka", "Tamil Nadu", "Kerala", "Andhra Pradesh", "Telangana"]
        else:
            for st in ["Karnataka", "Tamil Nadu", "Kerala", "Andhra Pradesh", "Telangana"]:
                if st.lower() in safe.lower():
                    locations.append(st)

        certs = []
        if "food-grade" in safe.lower() or "food grade" in safe.lower():
            certs.append("food-grade")

        min_capacity = None
        m = re.search(r"(\d{3,7})\s*(units|items|pcs|pieces)?", safe)
        if m:
            try:
                val = int(m.group(1))
                if val >= 100:
                    min_capacity = val
            except Exception:
                pass

        max_days = None
        m2 = re.search(r"within (\d{1,3}) days", safe.lower())
        if m2:
            try:
                max_days = int(m2.group(1))
            except Exception:
                pass

        req = ParsedRequirement(
            objective=user_request,
            entity_type="supplier",
            hard_constraints=HardConstraints(
                locations=locations,
                certifications=certs,
                minimum_capacity=min_capacity,
                maximum_delivery_days=max_days,
            ),
            preferences=Preferences(),
            requested_results=3,
            raw_request=safe,
        )
        return req
