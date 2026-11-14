# Reading an unverified pressure in FLEX

NASA’s Flame Extinguishment Experiment lists **0 mmHg** for ambient pressure in test **114**, run **C11M201**. The PSI-69 experimental table and NASA’s technical report both print zero. Those entries establish what was reported. The actual chamber pressure and the reason for the zero remain unverified.

Keep the printed **0 mmHg** visible as **reported, unverified**. Leave the numeric pressure unset and omit this run from pressure charts and threshold filters. For example, a search for runs below 8 psi would otherwise treat this entry as a confirmed low-pressure measurement. The measurements from nearby runs apply to those runs only.

Evidence review by [Osman](https://github.com/Osmankhurram).

- [NASA Physical Sciences Informatics, FLEX (PSI-69), experimental table, test 114](https://psi.nasa.gov/geode-py/ws/studies/PSI-69/download?file=6792be99b7b6ff8e65037e3a&version=1&studyVersion=5&redirect=true) · dataset DOI `10.60555/mbq8-0451`
- [NASA/TP—2015-216046, Table IX, printed page 22, FLEX–114](https://ntrs.nasa.gov/api/citations/20150023456/downloads/20150023456.pdf)
