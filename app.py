"""
The whole app in one file: type a name in, get back a whisper that's
spoken out loud, and a "why did you say that" button that shows the
actual reasoning. No build step, no frontend framework — just Flask
serving one HTML page and two JSON endpoints.
"""

import base64
import os
import time
from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

load_dotenv()

import db
import voice

app = Flask(__name__, static_folder="static")


def compose_whisper(facts):
    """
    Turn a ranked list of facts into a short whisper.

    We only ever speak the top 2 — that's the "whisper budget" from the
    architecture doc, a briefing you can absorb in the second it takes to
    walk up to someone, not a report. Whatever scored lower becomes the
    "alternatives we rejected" list on the Decision, so the reasoning is
    honest about what got left out and why.
    """
    if not facts:
        return "", 0.0, [], []

    spoken = facts[:2]
    rejected = facts[2:]

    whisper_text = " ".join(f["value"] for f in spoken)
    top_urgency = max(f.get("urgency_tag", 0.0) for f in spoken)

    facts_touched = [f["_id"] for f in spoken]
    alternatives = [
        {
            "option": f"Include '{f['key']}' fact",
            "rejected_because": (
                f"Score {f['urgency_score']:.2f} vs "
                f"{min(s['urgency_score'] for s in spoken):.2f} for the lowest spoken fact; "
                "would exceed the 2-sentence whisper budget."
            ),
        }
        for f in rejected
    ]
    return whisper_text, top_urgency, facts_touched, alternatives


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/whisper")
def whisper():
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    start = time.perf_counter()

    person = db.resolve_person(name)
    if not person:
        return jsonify({"error": f"No one named '{name}' found."}), 404

    facts = db.get_facts(person["_id"])
    whisper_text, urgency, facts_touched, alternatives = compose_whisper(facts)

    if not whisper_text:
        return jsonify({"error": f"No active facts on file for {person['name']}."}), 404

    audio_bytes = voice.speak(whisper_text, urgency)
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    decision_id = db.log_decision(
        {
            "decision_type": "recall_selection",
            "actor": "encounter_agent:v1",
            "choice": f"Whispered {len(facts_touched)} fact(s) for {person['name']}; omitted {len(alternatives)} lower-scoring fact(s).",
            "alternatives": alternatives,
            "reasoning": "Top facts by urgency-weighted score (0.3 recency + 0.5 urgency + 0.2 confidence).",
            "facts_touched": facts_touched,
            "parent_decision_id": None,
        }
    )

    return jsonify(
        {
            "person": person["name"],
            "whisper_text": whisper_text,
            "audio_base64": audio_b64,
            "elapsed_ms": elapsed_ms,
            "decision_id": str(decision_id),
        }
    )


def to_jsonable(value):
    """Walk a Mongo document and turn ObjectId/datetime into plain strings."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    return value


@app.route("/api/decision/<decision_id>")
def decision_chain(decision_id):
    try:
        oid = ObjectId(decision_id)
    except InvalidId:
        return jsonify({"error": "invalid decision id"}), 400

    result = db.get_decision_chain(oid)
    if not result:
        return jsonify({"error": "decision not found"}), 404

    return jsonify(to_jsonable(result))


@app.route("/api/architecture-decisions")
def architecture_decisions():
    """The capstone from the demo script: the system explaining its own build choices."""
    db_ = db.get_db()
    docs = list(db_.decisions.find({"decision_type": "architecture"}))
    return jsonify(to_jsonable(docs))


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
