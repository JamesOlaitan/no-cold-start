# No Cold Start

Every agent starts from nothing. This one doesn't.

Type a name in, and you get a short whisper spoken out loud about what
matters right now for that person — not everything you've ever noted
about them, just the one or two things worth knowing before you walk up
and say hi. Click "why did you say that?" and you get the real reason:
which facts got picked, which got left out, and the actual scoring
behind the choice.

## The idea

Most memory systems store one kind of thing: facts. This one stores two:

- **Facts** — what's true right now. Each one decays on its own
  half-life, gets a hand-set urgency, and gets superseded when something
  newer replaces it.
- **Decisions** — a record of a choice the system made, the alternatives
  it rejected, and why. Every whisper logs one. Every time an old fact
  gets replaced by a new one, that logs one too. Decisions can even point
  back to earlier decisions, so "why is it this way" can walk back
  through a whole chain of reasoning, not just one hop.

Both live in MongoDB Atlas. Facts get ranked with an aggregation
pipeline that scores recency (decayed on the fact's own half-life),
urgency, and confidence together. Decisions get walked backward with
`$graphLookup`. The voice comes from ElevenLabs, and the tone of the
voice itself changes with how urgent the fact is — a health scare sounds
different from a coffee order.

## Running it

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in your Atlas connection string and ElevenLabs API key
./.venv/bin/python seed.py       # loads sample people, facts, and decisions
./.venv/bin/python app.py        # starts the app on http://localhost:5000
```

Open `http://localhost:5000`, type a seeded name (e.g. "Frank" or
"Aisha"), and hit Whisper.

## Layout

- `db.py` — resolving a person, scoring their facts, writing new facts,
  logging decisions, and walking a decision chain.
- `voice.py` — turns whisper text into spoken audio, with the voice
  settings driven by the fact's urgency.
- `app.py` — the Flask app: one page, two JSON endpoints.
- `seed.py` — loads sample data, including a handful of "architecture"
  decisions where the system explains its own build choices.
- `static/index.html` — the whole UI: a name box, the whisper, an audio
  player, a stopwatch, and a "why" button.
