# Human-in-the-Loop AI Response Grading Platform

A human-in-the-loop platform for grading AI responses against rubrics and analysing reviewer disagreement.

## Features

- Authenticated workspaces, role-based access (Admin, Manager, Reviewer, Observer)
- Projects with descriptions, instructions, task types, goals, blind review, double-review policies
- Server-side authorization enforced in backend, not just UI hiding
- Side-by-side display of prompt, context, reference, Response A/B
- Safe rendering for code, Markdown, long responses
- Distinct scoring sections, issue reporting, notes, rationale
- Preference: Response A, Response B, Tie, Both Unacceptable (distinct semantics) + Skip

## Stack

Python, Django, pandas, NumPy, scikit-learn, Plotly, Pillow, pytest, Docker

## Clone

```bash
git clone https://github.com/sanjaymouraly/human-in-the-loop-ai-grading-platform.git
cd human-in-the-loop-ai-grading-platform
```

## Setup

```bash
# The project ships a Docker Compose setup.
docker compose up --build
```

See `docs/` or the compose file for environment variables and ports.

## Run

```bash
docker compose up --build
```

## Tests

```bash
pytest -q
```

## Notes

- Sample data, when included, is synthetic.

## License

MIT © 2023 [Sanjay Mouraly](https://github.com/sanjaymouraly)
