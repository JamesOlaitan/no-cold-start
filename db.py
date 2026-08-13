"""
All the MongoDB work lives here: finding a person, scoring their facts,
writing new facts, and logging + walking back through decisions.

Facts are things we know ("Frank's dog had surgery"). Decisions are a
record of a choice the system made and why ("I whispered the dog-surgery
fact instead of the last-visit summary because it scored higher"). Keeping
decisions as their own documents, linked to the facts that fed them, is
what makes "why did you say that" answerable instead of just implied.
"""

import os
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.errors import OperationFailure

_client = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        uri = os.environ["MONGODB_URI"]
        _client = MongoClient(uri)
        _db = _client[os.environ.get("MONGODB_DB", "no_cold_start")]
    return _db


def resolve_person(name: str):
    """
    Find a person by name. We try Atlas Search first because it's
    typo-tolerant (great for a live demo where someone fat-fingers a
    name). If the search index isn't built yet, we fall back to a plain
    case-insensitive match so the demo never just breaks.
    """
    db = get_db()
    try:
        pipeline = [
            {
                "$search": {
                    "index": "people_name_search",
                    "text": {"query": name, "path": "name", "fuzzy": {"maxEdits": 2}},
                }
            },
            {"$limit": 1},
        ]
        results = list(db.people.aggregate(pipeline))
        if results:
            return results[0]
    except OperationFailure:
        pass

    return db.people.find_one({"name": {"$regex": f"^{name}", "$options": "i"}})


def get_facts(subject_id, top_k=4):
    """
    Score every active fact for this person and return the top few.

    A fact matters more the more urgent it was hand-tagged, the more
    confident we are in it, and the more recently it was confirmed —
    but "recently" decays on a per-fact half-life, so a fact about a
    week-long recovery stays relevant longer than one about today's mood.
    Weights (0.3 recency, 0.5 urgency, 0.2 confidence) match the
    architecture doc: urgency should dominate recency.
    """
    db = get_db()
    pipeline = [
        {"$match": {"subject_id": subject_id, "status": "active"}},
        {
            "$addFields": {
                "days_since": {
                    "$divide": [
                        {"$subtract": ["$$NOW", "$last_confirmed_at"]},
                        86400000,
                    ]
                }
            }
        },
        {
            "$addFields": {
                "recency_score": {
                    "$exp": {
                        "$multiply": [
                            -1,
                            {
                                "$divide": [
                                    {"$multiply": [{"$ln": [2]}, "$days_since"]},
                                    "$half_life_days",
                                ]
                            },
                        ]
                    }
                }
            }
        },
        {
            "$addFields": {
                "urgency_score": {
                    "$add": [
                        {"$multiply": [0.3, "$recency_score"]},
                        {"$multiply": [0.5, "$urgency_tag"]},
                        {"$multiply": [0.2, "$confidence"]},
                    ]
                }
            }
        },
        {"$sort": {"urgency_score": -1}},
        {"$limit": top_k},
    ]
    return list(db.facts.aggregate(pipeline))


def write_fact(fact: dict):
    """
    Save a new fact. If we already have a fact with the same (person,
    key) — e.g. two different notes both filed under "mood" — the old
    one is marked superseded instead of just sitting there stale. That
    reconciliation choice gets logged as its own Decision, so later you
    can ask "why did the old mood note disappear" and get a real answer.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    fact.setdefault("created_at", now)
    fact.setdefault("last_confirmed_at", now)
    fact.setdefault("status", "active")
    fact.setdefault("superseded_by", None)

    existing = db.facts.find_one(
        {"subject_id": fact["subject_id"], "key": fact["key"], "status": "active"}
    )

    result = db.facts.insert_one(fact)
    new_id = result.inserted_id

    if existing:
        db.facts.update_one(
            {"_id": existing["_id"]},
            {"$set": {"status": "superseded", "superseded_by": new_id}},
        )
        log_decision(
            {
                "decision_type": "reconciliation",
                "actor": "reconciliation_agent:v1",
                "choice": f"Superseded prior '{fact['key']}' fact with the new one.",
                "alternatives": [
                    {
                        "option": "Keep both as separate active facts",
                        "rejected_because": "Same (subject_id, key) pair — treated as an update, not a new fact.",
                    }
                ],
                "reasoning": "Rule: a new fact sharing (subject_id, key) with an active fact replaces it.",
                "facts_touched": [existing["_id"], new_id],
                "parent_decision_id": None,
            }
        )

    return new_id


def log_decision(decision: dict):
    db = get_db()
    decision.setdefault("timestamp", datetime.now(timezone.utc))
    decision.setdefault("parent_decision_id", None)
    result = db.decisions.insert_one(decision)
    return result.inserted_id


def get_decision_chain(decision_id):
    """Walk a decision back through its parents and expand the facts each one touched."""
    db = get_db()
    pipeline = [
        {"$match": {"_id": decision_id}},
        {
            "$graphLookup": {
                "from": "decisions",
                "startWith": "$parent_decision_id",
                "connectFromField": "parent_decision_id",
                "connectToField": "_id",
                "as": "decision_chain",
            }
        },
        {
            "$lookup": {
                "from": "facts",
                "localField": "facts_touched",
                "foreignField": "_id",
                "as": "facts_expanded",
            }
        },
    ]
    results = list(db.decisions.aggregate(pipeline))
    return results[0] if results else None
