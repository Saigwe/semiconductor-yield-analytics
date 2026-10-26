# 3-minute walkthrough: Semiconductor Yield & Test Analytics

A timed script for a Loom recording of about 3 minutes (screen plus camera bubble, 1080p). Say it in your own words; the lines are a guide, not a teleprompter.

> **Before recording:** Record this one only after the real SECOM run is done and [Numbers](../README.md#numbers) is filled. Today the repo is scaffolded and proven on a fixture, and the script below says so. Re-record when the roadmap items land.

**Open these tabs before you press record:** README, docs/layer_plan.md, dbt/models, nl2sql/, GitHub Actions.

| Time | On screen | What to say |
|---|---|---|
| 0:00–0:20 | Portfolio card, then the README title | Fabs log 590 sensor readings per wafer run, and yield dashboards built on raw tables disagree. I built a governed lakehouse that defines yield once, ranks suspect sensors, and answers plain-English questions with SQL that's checked against a benchmark. |
| 0:20–0:45 | README intro and the Data section | I'm an electrical and electronic engineer by training (BEng, MSc), and I've spent nine years making numbers trustworthy for finance and operations teams. This project puts the two together on UCI's public SECOM data. The lots, tools and sensor names are synthetic because SECOM is anonymised. |
| 0:45–1:10 | README architecture diagram, then `docs/layer_plan.md` | Bronze keeps the raw readings. Silver types them and gives every table an explicit grain. Gold has one yield definition that every dashboard reads. |
| 1:10–1:35 | A gold model and its tests in `dbt/` | Business-rule tests catch outputs that are technically valid but wrong: yield must sit between 0 and 1, fails can't exceed wafers, and every wafer must have readings. |
| 1:35–2:00 | `nl2sql/` | The plain-English layer may only run a single SELECT against approved gold models, and it's scored on execution accuracy against hand-written SQL. |
| 2:00–2:30 | CI badge and the latest Actions run | On the fixture, dbt passes 72 of 72 checks, and the fail-signal report ranks the two sensors I deliberately shifted first. That's how I know the ranking works before trusting it on real data. |
| 2:30–2:45 | `docs/design_doc.md`, the options table | The decision I'd defend in an interview: I gave each layer a grain before writing any SQL, because most metric disagreements I've fixed in my career came from joins at the wrong grain. |
| 2:45–3:00 | Back to the README top | For a manufacturing or analytics team, that means one yield number, a short list of sensors to check, and an AI interface that refuses rather than guesses. The repo, numbers and design doc are linked under the video. |

## Recording checklist
- Close email, chat and notifications. Zoom the browser to 125% so code is readable.
- Run `make fixture-all` once before recording, so CI-style output is fresh if you show it.
- Keep to one take per section; Loom lets you trim. Aim for 2:45 to 3:10.
- Show real numbers on screen as you say them; never estimate on camera.
- Say "synthetic" out loud wherever the README labels data as synthetic.

## After recording
1. Copy the Loom share link.
2. In `README.md`, replace the roadmap line with `- [x] [3-minute Loom walkthrough](<your Loom link>)` and add the link under the title.
3. Add the link to this project's card on saigwe.github.io.
