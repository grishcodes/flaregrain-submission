# Reading a disputed measurement in Saffire I-1

Flaregrain marks a field as disputed when two sources report values that cannot be reconciled from the evidence available. For the Saffire I-1 sample thickness, start with the number and the unit in each original source.

| Source | What it reports |
| --- | --- |
| [NASA investigator presentation, Table I, PDF page 29](https://ntrs.nasa.gov/api/citations/20170008805/downloads/20170008805.pdf#page=29) | Run `1-1` lists the cotton–fiberglass sample thickness as **0.37 mm**. |
| [NASA PSI-98, Saffire-I experimental table, row S1](https://psi.nasa.gov/geode-py/ws/studies/PSI-98/download?file=6792c46eb7b6ff8e65037f3e&version=1&studyVersion=4&redirect=true) | Row `S1` lists **0.37** under the heading **Sample Thickness (cm)**. |

Check the unit even when the printed numbers match. A literal reading of the CSV header would make that entry 3.7 mm. That calculation illustrates the discrepancy. The available records do not resolve which thickness to use, so keep the two entries visible and leave the comparison’s preferred thickness unset.

A missing value is a separate case. In the [BASS-II summary, Table A.1, PDF page 111](https://ntrs.nasa.gov/api/citations/20210011385/downloads/TM-20210011385.pdf#page=111), the B1 row describes rapid extinction after airflow stopped and gives no elapsed time for that interval. Show the observed outcome and leave the numeric delay unavailable.
