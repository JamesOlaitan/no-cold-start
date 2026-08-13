"""
Fills the database with fake people, facts about them, and a few
"architecture" decisions that explain why we built the app the way we
did. Run this once before the demo: `python seed.py`

It wipes the three collections first so you can re-run it safely if you
mess something up live.
"""

from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

import db

now = datetime.now(timezone.utc)


def days_ago(n):
    return now - timedelta(days=n)


PEOPLE = [
    "Frank Delgado",
    "Maria Ibarra",
    "Tobi Adeyemi",
    "Elena Petrova",
    "Sam Nakamura",
    "Priya Raman",
    "Doug Fenwick",
    "Aisha Bello",
]

# (name, key, value, urgency_tag, confidence, half_life_days, days_since_confirmed)
FACTS = [
    ("Frank Delgado", "dog_surgery", "Frank's dog had knee surgery last week; he's been anxious about the recovery.", 0.85, 0.9, 21, 6),
    ("Frank Delgado", "relationship", "Frank is your neighbor of eight years and waters your plants when you travel.", 0.4, 1.0, 365, 40),
    ("Frank Delgado", "coffee_order", "Frank always orders a black coffee, no sugar.", 0.15, 0.9, 90, 30),
    ("Frank Delgado", "job_change", "Frank just started a new job as a electrician after being laid off in the spring.", 0.6, 0.85, 45, 10),

    ("Maria Ibarra", "surgery_recovery", "Maria had knee replacement surgery two weeks ago and is still on crutches.", 0.9, 0.95, 30, 14),
    ("Maria Ibarra", "grandchild_visit", "Maria's granddaughter is visiting from out of state this weekend.", 0.7, 0.9, 5, 1),
    ("Maria Ibarra", "relationship", "Maria is your book club co-founder; you've known her for six years.", 0.35, 1.0, 365, 60),

    ("Tobi Adeyemi", "job_loss", "Tobi was laid off last month and has been job hunting; bring it up gently.", 0.8, 0.9, 40, 12),
    ("Tobi Adeyemi", "hobby", "Tobi just picked up woodworking and is proud of a bookshelf he finished.", 0.3, 0.8, 60, 8),
    ("Tobi Adeyemi", "relationship", "Tobi is your college roommate's younger brother.", 0.25, 0.95, 365, 90),

    ("Elena Petrova", "health_scare", "Elena had a minor heart scare three days ago; doctors said it's stress-related.", 0.95, 0.9, 14, 3),
    ("Elena Petrova", "pet", "Elena adopted a rescue cat named Boris last month.", 0.2, 0.85, 60, 20),
    ("Elena Petrova", "relationship", "Elena is your former manager, now a close friend.", 0.3, 1.0, 365, 50),

    ("Sam Nakamura", "wedding", "Sam is getting married in three weeks and is stressed about the seating chart.", 0.75, 0.9, 25, 5),
    ("Sam Nakamura", "diet", "Sam recently went vegetarian and appreciates when restaurants have options.", 0.25, 0.8, 90, 15),
    ("Sam Nakamura", "relationship", "Sam is your cousin's best friend; you see him at family events.", 0.2, 0.9, 365, 100),

    ("Priya Raman", "move", "Priya just moved into a new apartment and is still unpacking.", 0.55, 0.85, 20, 4),
    ("Priya Raman", "promotion", "Priya got promoted to team lead two weeks ago.", 0.5, 0.9, 30, 12),
    ("Priya Raman", "relationship", "Priya is your gym buddy; you two train together on weekends.", 0.2, 0.95, 365, 30),

    ("Doug Fenwick", "injury", "Doug sprained his ankle hiking last weekend and is on crutches for two weeks.", 0.7, 0.9, 14, 4),
    ("Doug Fenwick", "hobby", "Doug has been learning to brew his own beer; ask how the latest batch turned out.", 0.2, 0.75, 60, 25),
    ("Doug Fenwick", "relationship", "Doug is your neighbor's husband; friendly but you don't know him well.", 0.15, 0.8, 365, 70),

    ("Aisha Bello", "bereavement", "Aisha's father passed away six days ago; she's back from the funeral this week.", 0.98, 0.95, 30, 6),
    ("Aisha Bello", "work_trip", "Aisha is traveling for work next week and mentioned she's nervous about the trip.", 0.4, 0.7, 10, 2),
    ("Aisha Bello", "relationship", "Aisha is a close friend from graduate school.", 0.3, 1.0, 365, 45),
]

ARCHITECTURE_DECISIONS = [
    {
        "decision_type": "architecture",
        "actor": "team:no_cold_start",
        "choice": "Used MongoDB Atlas as the single memory store instead of stitching together a vector database plus a separate relational store.",
        "alternatives": [
            {
                "option": "Pinecone/Weaviate for embeddings + Postgres for structured Decision records",
                "rejected_because": "Two systems means two sources of truth and no single query that walks a Decision back through the Facts it touched.",
            }
        ],
        "reasoning": "Aggregation pipelines score Facts by urgency in one query, and $graphLookup walks a Decision chain in one query, in the same database the vector index lives in.",
        "facts_touched": [],
        "parent_decision_id": None,
    },
    {
        "decision_type": "architecture",
        "actor": "team:no_cold_start",
        "choice": "Picked ElevenLabs Flash v2.5 streaming over the higher-quality standard model.",
        "alternatives": [
            {
                "option": "eleven_multilingual_v2 (higher audio quality, blocking generate call)",
                "rejected_because": "Time-to-first-audio matters more than polish for a whisper you hear seconds before an encounter; the 2-second budget doesn't leave room for a slower model.",
            }
        ],
        "reasoning": "Flash v2.5's streaming endpoint gets audio starting around 260-300ms into the request, leaving margin for the DB query and whisper composition inside a 2-second total budget.",
        "facts_touched": [],
        "parent_decision_id": None,
    },
    {
        "decision_type": "architecture",
        "actor": "team:no_cold_start",
        "choice": "Gave every fact its own half-life instead of one global decay rate for all facts.",
        "alternatives": [
            {
                "option": "Single fixed decay window (e.g. all facts fade after 30 days)",
                "rejected_because": "A surgery recovery still matters after three weeks; a passing mood note doesn't matter after three days. One rate would get both wrong.",
            }
        ],
        "reasoning": "Per-fact half_life_days lets urgent, long-lasting facts (health, grief) stay ranked highly longer than routine ones (coffee order, small talk topics), without hand-tuning urgency alone to compensate.",
        "facts_touched": [],
        "parent_decision_id": None,
    },
    {
        "decision_type": "architecture",
        "actor": "team:no_cold_start",
        "choice": "Built a one-shot 'name in, whisper out' flow instead of a conversational chatbot.",
        "alternatives": [
            {
                "option": "Conversational agent you can ask follow-up questions",
                "rejected_because": "The real use case is seconds before you greet someone, not a back-and-forth chat window you have open in advance.",
            }
        ],
        "reasoning": "A direct streaming TTS call on a resolved name is simpler than a dialogue loop and matches how the briefing actually gets used.",
        "facts_touched": [],
        "parent_decision_id": None,
    },
]


def run():
    database = db.get_db()

    print("Clearing existing collections...")
    database.people.delete_many({})
    database.facts.delete_many({})
    database.decisions.delete_many({})

    print(f"Inserting {len(PEOPLE)} people...")
    name_to_id = {}
    for name in PEOPLE:
        result = database.people.insert_one({"name": name, "created_at": now})
        name_to_id[name] = result.inserted_id

    print(f"Inserting {len(FACTS)} facts...")
    for name, key, value, urgency, confidence, half_life, since in FACTS:
        database.facts.insert_one(
            {
                "subject_id": name_to_id[name],
                "subject_type": "person",
                "key": key,
                "value": value,
                "origin": {
                    "source_type": "caregiver_input",
                    "actor": "seed_script",
                    "recorded_at": days_ago(since),
                },
                "urgency_tag": urgency,
                "confidence": confidence,
                "half_life_days": half_life,
                "status": "active",
                "superseded_by": None,
                "created_at": days_ago(since),
                "last_confirmed_at": days_ago(since),
            }
        )

    print(f"Inserting {len(ARCHITECTURE_DECISIONS)} architecture decisions...")
    for decision in ARCHITECTURE_DECISIONS:
        db.log_decision(decision)

    print("Done. Try: python -c \"import db; print(db.resolve_person('Frank'))\"")


if __name__ == "__main__":
    run()
