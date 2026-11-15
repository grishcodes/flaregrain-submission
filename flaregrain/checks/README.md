# Flaregrain checks

What the team runs to check Flaregrain, and what each check needs. Run everything from the repository root.

## Run with this repository alone

| Check | Command | Needs |
|---|---|---|
| Submission tests: the static Compare build, its data and its NASA links | `python3 -I flaregrain/tests/run.py` | Python 3.9+ |
| Build check | `python3 -I flaregrain/build.py --check` | Python 3.9+ |
| NASA data rebuild: fetches PSI and the 9 reports, rebuilds every data file, compares the counts | `python3 -I flaregrain/intake/rebuild.py --reports --strict` | Python 3.9+, network, poppler (`pdftotext`, `pdfinfo`) |

## Checker stress test

`checker_stress.mjs` tests the sentence checker, the rule that keeps a model sentence only if it matches the record fields it cites. For every pair of the 11 comparable checked records it builds sentences from the records' real facts:

- **good** sentences restate a cited fact and should pass
- **bad** sentences carry one known defect (a wrong number or unit, the other record's fact, a cause word, no citation, an invented detail, a disputed value stated as fact, and more) and should be removed

It reports, by class, the bad sentences that pass and the good ones that are removed.

    node flaregrain/checks/checker_stress.mjs "<built dashboard page>" out.json

**Needs:** Node 18 or later, and **a built Flaregrain dashboard page**: the full-data app that holds the checker, `checkSentence()`. That page is the team's private demo build, and its source is not in this repository yet, so this check cannot run from this repository alone today. `page-logic.mjs` loads the page's own script in a Node `vm`, the same way the team's model proxy does, so the test exercises the code users get. No browser, no network; about 15 seconds.

**Latest result** (`checker-stress-result.json`, built dashboard of November 15; the same counts as the team's Mac Mini run of November 14 after its two fixes):

| | |
|---|---|
| Sentences | 343,758 (35,186 good, 308,572 bad) over 55 record pairs |
| Missed: wrong number, the other record's fact, cause word, no citation, fact ID left in text, "respectively", disputed value stated as fact | **0** |
| Missed: wrong unit | 240 of 4,480 per sentence framing (920 before the fixes) |
| Missed: false absence ("X does not report …") | 320 of 5,760 |
| Missed: unlike quantities set against each other | 60 of 834 per framing |
| Missed: invented detail | 19,520 of 23,040 per framing: the known gap. An invented detail that reuses words from the cited fields usually passes, so model text is always labelled as Flaregrain's reading and never styled as NASA evidence |
| Good sentences removed (false alarms) | 5,448 of 35,186 |

The original Mac Mini harness drove the same sentence generator through a browser against an instrumented copy of the page. This port keeps the generator unchanged and calls the checker directly; on the same build it gives identical counts.

## Run by the team on the private build

These need the full-data dashboard or the team's machines. They are listed so nothing is hidden; they are not in this repository.

| Check | What it covers | Needs |
|---|---|---|
| Regression checks (22) | the dashboard's evidence rules, record fields, Compare for all 110 ordered pairs, Habitat, System design | Playwright (Chromium), private build |
| Browser journeys (2) | Ask → cited answer → Compare → back; Browse → original PDF → Evidence trace | Playwright, private build |
| Evaluation | rules-only ranking over 30 questions × 4 wordings: recall@5 0.850, hit@1 0.833 | Playwright, private build, the draft question set |
| Model checks | the local model's saved explanations, re-checked sentence by sentence | Playwright, private build, Ollama with qwen3:4b |
| Redesign parity and browser checks | Nora's pages answered without a server, compared with her prototype server (195 requests, 16 browser checks) | Node, Playwright, private build, Nora's prototype |
| Model proxy check | the Mac Mini proxy's refusals, a real pair and its rate limit | the Mac Mini, Ollama |
