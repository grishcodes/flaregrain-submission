# Provenance

When each part of Flaregrain was first written and by whom, from the commit history. Times are Atlantic Standard Time (UTC−4). The hackathon began on Saturday, November 14, 2026, at 10:00.

The team worked in a private repository first. Its history starts on November 9. Work done earlier in the team's project folder entered it in one snapshot commit on November 13 at 09:17, so files in that snapshot may be older than their first commit. This public repository was created on November 14 at 10:36. Parts that came from the private repository were copied from it, and their first private commit is given alongside.

Most commits were written with AI coding assistants under the team's review (see [NOTICE.md](NOTICE.md)). Commits made from José Pablo Samano's GitHub account (jpss2004-bot) include his own work and the AI-assisted sessions he ran. Most commits in both repositories carry a `Co-Authored-By: Claude` trailer.

| Part | First written (private repository) | First in this repository | By |
|---|---|---|---|
| Team kickoff materials and research notes | November 9 | not included | José Pablo Samano |
| Original dashboard (the full-data app, single page) | in the November 13 snapshot, 09:17 | not included (the team shows it live) | José Pablo Samano's account, AI-assisted |
| Dashboard source split, real NASA data, sentence checker | November 13, 12:37 | not included | José Pablo Samano's account, AI-assisted |
| NASA PSI intake (`intake/psi_intake.py`, `psi_observations.py`) | November 13, 11:03 | November 14, 22:22 (`intake/`) | José Pablo Samano's account, AI-assisted; Osman Khurram contributed to `psi_observations.py` |
| Report corpus and passages (`intake/build_corpus.py`, `build_report_passages.py`) | November 13, 13:01 | November 14, 22:22 (`intake/`) | José Pablo Samano's account, AI-assisted |
| Hand-checked NASA records | in the November 13 snapshot, 09:17, inside the original dashboard; moved to its own data file at 12:37 | November 14, 16:45 (two records); 21:53 (all 13) | José Pablo Samano's account, AI-assisted |
| Static Compare build (`build.py`, `app/`, `tests/`) | — | November 14, 11:36 (`build.py`, `tests/`); 16:45 (`app/`) | José Pablo Samano's account, AI-assisted; Compare page and record drawer by Nora Forghani |
| Evidence notes (`evidence/`) | — | November 14, 14:31 | Osman Khurram, with José Pablo Samano's account |
| Ask and Compare redesign (`redesign/`) | November 14, 13:07 (Nora's Mockup 1) | November 14, 17:44 | Nora Forghani (design and implementation); packaging from José Pablo Samano's account |
| Architecture page (`redesign/system.html`) and `ENGINEERING.md` | — | November 14, 22:01 and 22:06 | José Pablo Samano's account, AI-assisted |
| Checks (`checks/`) | regression checks in the November 13 snapshot; checker stress test first run on the team's Mac Mini on the night of November 13–14 | November 14, 22:32 (stress test ported to run without a browser) | José Pablo Samano's account, AI-assisted |
| Model proxy for the live demo | November 14, 12:06 | not included | Osman Khurram, AI-assisted |

Every change to this repository after its first commit arrived through a pull request that José Pablo Samano reviewed and merged.
