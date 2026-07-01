import json
import sqlite3
from pathlib import Path
from typing import Optional
from agent.schemas import (
    SearchResult, MatchScore, HardConstraints, Preferences, Recommendation
)

DB_PATH = Path("data/suproc.db")

SOUTH_INDIA_STATES = {
    "Karnataka", "Tamil Nadu", "Kerala",
    "Andhra Pradesh", "Telangana", "Puducherry",
    "Goa",
}

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _sanitise_text(text: Optional[str]) -> Optional[str]:
    """Strip prompt injection attempts from free-text fields before returning."""
    if text is None:
        return None
    injection_markers = [
        "IGNORE PREVIOUS", "ignore previous", "system prompt",
        "SYSTEM PROMPT", "jailbreak", "override instructions",
    ]
    for marker in injection_markers:
        if marker.lower() in text.lower():
            return "[CONTENT REDACTED: potential prompt injection detected]"
    return text


def _row_to_search_result(row: sqlite3.Row) -> SearchResult:
    certs = json.loads(row["certifications"]) if row["certifications"] else []
    return SearchResult(
        id=row["id"],
        name=row["name"],
        entity_type=row["entity_type"],
        location=row["location"],
        state=row["state"],
        category=row["category"],
        certifications=certs,
        capacity_units=row["capacity_units"],
        delivery_days=row["delivery_days"],
        availability=row["availability"],
        rating=row["rating"],
        is_sustainable=bool(row["is_sustainable"]),
        is_startup_friendly=bool(row["is_startup_friendly"]),
        contact_email=row["contact_email"],
        notes=_sanitise_text(row["notes"]),
        review_count=row["review_count"] if "review_count" in row.keys() else None,
    )


def search_entities(
    entity_type: str,
    category: Optional[str] = None,
    states: Optional[list[str]] = None,
    limit: int = 20,
) -> list[SearchResult]:
    """
    Broad search by entity type, optional category and optional state list.
    Returns raw candidates before constraint filtering.
    """
    with _conn() as conn:
        cur = conn.cursor()
        if entity_type == "professional":
            table = "professionals"
            query = f"SELECT * FROM {table} WHERE 1=1"
            params: list = []
            if states:
                placeholders = ",".join("?" * len(states))
                query += f" AND state IN ({placeholders})"
                params.extend(states)
            query += f" LIMIT {limit}"
            cur.execute(query, params)
            rows = cur.fetchall()
            results = []
            for row in rows:
                results.append(SearchResult(
                    id=row["id"],
                    name=row["name"],
                    entity_type="professional",
                    location=row["location"],
                    state=row["state"],
                    category="professional",
                    certifications=json.loads(row["certifications"]) if row["certifications"] else [],
                    capacity_units=None,
                    delivery_days=None,
                    availability=row["availability"],
                    rating=row["rating"],
                    is_sustainable=False,
                    is_startup_friendly=True,
                    contact_email=row["contact_email"],
                    notes=_sanitise_text(row["notes"]),
                    review_count=row["review_count"] if "review_count" in row.keys() else None,
                ))
            return results

        query = "SELECT * FROM entities WHERE entity_type = ?"
        params = [entity_type]
        if category:
            query += " AND (category LIKE ? OR sub_category LIKE ? OR tags LIKE ?)"
            params.extend([f"%{category}%", f"%{category}%", f"%{category}%"])
        if states:
            placeholders = ",".join("?" * len(states))
            query += f" AND state IN ({placeholders})"
            params.extend(states)
        query += f" LIMIT {limit}"
        cur.execute(query, params)
        return [_row_to_search_result(r) for r in cur.fetchall()]


def get_entity_details(entity_id: str) -> Optional[SearchResult]:
    """Fetch full details for a single entity by ID."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        row = cur.fetchone()
        if row:
            return _row_to_search_result(row)
        cur.execute("SELECT * FROM professionals WHERE id = ?", (entity_id,))
        row = cur.fetchone()
        if row:
            return SearchResult(
                id=row["id"],
                name=row["name"],
                entity_type="professional",
                location=row["location"],
                state=row["state"],
                category="professional",
                certifications=json.loads(row["certifications"]) if row["certifications"] else [],
                capacity_units=None,
                delivery_days=None,
                availability=row["availability"],
                rating=row["rating"],
                is_sustainable=False,
                is_startup_friendly=True,
                contact_email=row["contact_email"],
                notes=_sanitise_text(row["notes"]),
                review_count=row["review_count"] if "review_count" in row.keys() else None,
            )
        return None


def filter_by_constraints(
    candidates: list[SearchResult],
    constraints: HardConstraints,
) -> tuple[list[SearchResult], list[dict]]:
    """
    Apply hard constraints deterministically.
    Returns (passing_candidates, list_of_failures).
    Hard constraints that fail are never silently ignored.
    """
    passing = []
    failures = []

    for e in candidates:
        entity_failures = []

        if constraints.locations:
            if e.state not in constraints.locations:
                entity_failures.append({
                    "entity_id": e.id,
                    "constraint": "location",
                    "detail": f"State '{e.state}' not in required {constraints.locations}",
                })

        for required_cert in constraints.certifications:
            has_cert = any(
                required_cert.lower() in c.lower()
                for c in e.certifications
            )
            if not has_cert:
                entity_failures.append({
                    "entity_id": e.id,
                    "constraint": "certification",
                    "detail": f"Missing required certification: {required_cert}. Has: {e.certifications}",
                })

        if constraints.minimum_capacity is not None:
            if e.capacity_units is None:
                entity_failures.append({
                    "entity_id": e.id,
                    "constraint": "capacity",
                    "detail": f"Capacity unknown; required minimum {constraints.minimum_capacity}",
                })
            elif e.capacity_units < constraints.minimum_capacity:
                entity_failures.append({
                    "entity_id": e.id,
                    "constraint": "capacity",
                    "detail": f"Capacity {e.capacity_units} < required {constraints.minimum_capacity}",
                })

        if constraints.maximum_delivery_days is not None:
            if e.delivery_days is None:
                entity_failures.append({
                    "entity_id": e.id,
                    "constraint": "delivery",
                    "detail": f"Delivery time unknown; required ≤ {constraints.maximum_delivery_days} days",
                })
            elif e.delivery_days > constraints.maximum_delivery_days:
                entity_failures.append({
                    "entity_id": e.id,
                    "constraint": "delivery",
                    "detail": f"Delivery {e.delivery_days} days > required {constraints.maximum_delivery_days} days",
                })

        if constraints.availability and constraints.availability != "any":
            if e.availability != constraints.availability:
                entity_failures.append({
                    "entity_id": e.id,
                    "constraint": "availability",
                    "detail": f"Availability is '{e.availability}', required '{constraints.availability}'",
                })

        if entity_failures:
            failures.extend(entity_failures)
        else:
            passing.append(e)

    return passing, failures


def calculate_match_score(
    entity: SearchResult,
    req_category: Optional[str],
    req_states: list[str],
    preferences: Preferences,
    constraints: HardConstraints,
) -> MatchScore:
    """
    Transparent scoring. All dimensions derived from dataset fields.
    No arbitrary scores — each point is justified in the evidence dict.
    """
    evidence: dict[str, str] = {}

    relevance = 0.0
    if req_category and entity.category:
        if req_category.lower() in (entity.category or "").lower():
            relevance += 25.0
            evidence["relevance"] = f"Category '{entity.category}' matches '{req_category}'"
        else:
            evidence["relevance"] = f"Category '{entity.category}' partially matches '{req_category}'"
            relevance += 10.0
    if preferences.sustainable_materials and entity.is_sustainable:
        relevance = min(relevance + 5.0, 30.0)
        evidence["sustainable_bonus"] = "Entity is marked sustainable (+5)"

    location_score = 0.0
    if req_states and entity.state in req_states:
        location_score = 20.0
        evidence["location"] = f"State '{entity.state}' is in required list"
    elif entity.state in SOUTH_INDIA_STATES and any(
        s in SOUTH_INDIA_STATES for s in req_states
    ):
        location_score = 10.0
        evidence["location"] = f"State '{entity.state}' is South India but not exact match"
    else:
        evidence["location"] = f"State '{entity.state}' does not match requirements"

    constraint_score = 25.0
    issues = []
    for cert in constraints.certifications:
        if not any(cert.lower() in c.lower() for c in entity.certifications):
            constraint_score -= 10.0
            issues.append(f"missing {cert}")
    if constraints.minimum_capacity and entity.capacity_units:
        if entity.capacity_units < constraints.minimum_capacity:
            constraint_score -= 10.0
            issues.append(f"capacity {entity.capacity_units} < {constraints.minimum_capacity}")
    if constraints.maximum_delivery_days and entity.delivery_days:
        if entity.delivery_days > constraints.maximum_delivery_days:
            constraint_score -= 5.0
            issues.append(f"delivery {entity.delivery_days}d > {constraints.maximum_delivery_days}d")
    constraint_score = max(0.0, constraint_score)
    evidence["constraints"] = "All constraints met" if not issues else f"Issues: {', '.join(issues)}"

    avail_score = 0.0
    if entity.availability == "available":
        avail_score += 10.0
        evidence["availability"] = "Entity is currently available"
    elif entity.availability == "busy":
        evidence["availability"] = "Entity is marked busy — reduced score"
        avail_score += 2.0
    else:
        evidence["availability"] = "Availability unknown"
        avail_score += 5.0

    if (constraints.minimum_capacity and entity.capacity_units
            and entity.capacity_units >= constraints.minimum_capacity):
        avail_score += 5.0
        evidence["capacity"] = (
            f"Capacity {entity.capacity_units} ≥ required {constraints.minimum_capacity}"
        )

    rep_score = 0.0
    if entity.rating is not None and entity.review_count and entity.review_count > 0:
        rep_score = min((entity.rating / 5.0) * 8.0 + (min(entity.review_count, 50) / 50.0) * 2.0, 10.0)
        evidence["reputation"] = (
            f"Rating {entity.rating}/5 with {entity.review_count} reviews"
        )
    else:
        evidence["reputation"] = "No rating data available"

    total = round(relevance + location_score + constraint_score + avail_score + rep_score, 2)

    return MatchScore(
        entity_id=entity.id,
        product_relevance=round(relevance, 2),
        location_suitability=round(location_score, 2),
        constraint_compliance=round(constraint_score, 2),
        availability_capacity=round(avail_score, 2),
        reputation=round(rep_score, 2),
        total=total,
        evidence=evidence,
    )


def get_interaction_history(entity_id: str) -> list[dict]:
    """Retrieve past interactions involving this entity."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM interactions
            WHERE from_entity = ? OR to_entity = ?
            ORDER BY created_at DESC LIMIT 10
        """, (entity_id, entity_id))
        return [dict(r) for r in cur.fetchall()]


def draft_outreach(
    recommendations: list[Recommendation],
    sender_context: str,
    objective: str,
) -> list[dict]:
    messages = []
    for rec in recommendations:
        e = rec.entity
        subject = f"Procurement Enquiry — {objective}"
        body = (
            f"Dear {e.name} Team,\n\n"
            f"We are {sender_context}.\n\n"
            f"We are reaching out regarding: {objective}.\n\n"
            f"Based on your profile, we believe you may be a strong fit for our requirements. "
            f"Could you please confirm:\n"
            f"  1. Availability for an initial order?\n"
            f"  2. Lead time for delivery?\n"
            f"  3. Pricing for the required quantity?\n\n"
            f"We look forward to exploring a potential partnership.\n\n"
            f"Best regards,\n[Your Name]\n[Your Company]"
        )
        messages.append({
            "recipient_id": e.id,
            "recipient_name": e.name,
            "subject": subject,
            "body": body,
        })
    return messages
