# 3-minute walkthrough: Semiconductor Yield & Test Analytics

A timed script for a Loom recording of about 3 minutes (screen plus camera bubble, 1080p). Say it in your own words; the lines are a guide, not a teleprompter.

**Open these tabs before you press record:** Dashboard, README, results/guardrail.md, dbt/models/intermediate, GitHub Actions.

| Time | On screen | What to say |
|---|---|---|
| 0:00–0:20 | Portfolio card, then the README title | 1,567 real wafer test runs, 590 sensors each, 93.4% yield. Which sensors actually separate failing wafers, and which wafers should an engineer look at first? This lakehouse answers both, and is honest about what doesn't work. |
| 0:20–0:45 | README intro and the Data section | I'm an electrical and electronic engineer by training (BEng, MSc), and I've spent nine years making numbers trustworthy for finance and operations teams. This puts the two together on UCI's real SECOM data. Pass/fail and readings are real; lots, tools and sensor names are synthetic because SECOM is anonymised. |
| 0:45–1:10 | The dashboard at saigwe.github.io/reports/semiconductor-yield: KPIs and the p-chart | Yield is defined once in dbt. The p-chart's limits come from the first half of runs, and 4 of 86 days break the upper limit. |
| 1:10–1:35 | The sensor Pareto, coloured by evidence | With 440 sensors, some look different by chance. Only 3 pass both a false-discovery check and a label-shuffle check, so the top-10 list alone would mislead. |
| 1:35–2:00 | The drift chart, then the ranking table | Passing wafers trip more than twice as many limits in the later half: the process drifted. Models fitted once do no better than chance; refitting every 100 wafers reaches 3x the base rate. |
| 2:00–2:30 | `results/guardrail.md`, then `int_sensor_stats.sql` and its unit test | The NL-to-SQL guardrail uses DuckDB's own parser and blocks 20 of 20 attacks; the regex it replaced let 6 through, including a comma join to raw data. A unit test proves later and failing wafers can't move the control limits. |
| 2:30–2:45 | `docs/design_doc.md`, the options table | The decision I'd defend in an interview: Score every method on later wafers it never saw, and report all of them, because a random split would hide the drift that matters most in a fab. |
| 2:45–3:00 | Back to the README top | For a manufacturing team, that means one yield number, three sensors worth chasing, a triage list that works, and an AI interface that can't escape the gold layer. The repo, numbers and design doc are linked under the video. |

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
