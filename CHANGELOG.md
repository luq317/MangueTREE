# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-13

First public release. The date is updated at release time.

### Added

- Package layout under `src/manguetree/` with the engine modules (`io`, `species`, `validation`, `calc`, `charts`, `report`, `i18n`) and a `manguetree` console command.
- Input validation with a row-level report of errors and warnings, shown in the app and included in the Excel and PDF exports.
- Neotropical species table (ten taxa, four regions), with one unique two-letter code per taxon (Rm, Rr, Rx, Ag, As, Ab, Lg, Ce, Pr, Pb), the Pelliciera split into *P. rhizophorae* and *P. benthamii* (Duke 2020), and *A. germinans* added to Brazil South and Southeast (to Rio de Janeiro, Ximenes et al. 2016). Genus abbreviations resolve only where the region has a single species of the genus. Editable in the app. The table is provisional.
- Bilingual interface and exports (English by default, Portuguese optional).
- Robust reading of field files: column aliases in English and Portuguese, decimal comma, header detection, plot-area detection, CSV and TXT support.
- Example data from the Guaratiba mangrove and reference tests that compare the engine with the laboratory spreadsheet.
- Documentation: README, methods, user guide, data format, installers, citation file, contributing guide.
- Continuous integration with the test suite on Python 3.11 and 3.13, and desktop builds for Windows and macOS.

### Changed

- Holdridge complexity index corrected: two indices (DBH > 2.5 cm and DBH > 10 cm), each with the same cutoff for $d$ and $b$, as in Pool et al. (1977). Species richness counts identified species only.
- Heights (mean, standard deviation, minimum, maximum, canopy) use live stems only; heights that are zero or negative are excluded.
- Canopy height is the mean of the 10 tallest live heights, configurable through `canopy_n`.
- Stems without a resolved species stay in density and basal area and are excluded from the phytosociology table and richness.
- De Liocourt's quotient is reported without automatic interpretation.
- DBH classes are closed on the left, as in the laboratory spreadsheet.
- Dependencies are pinned in `requirements.txt`; Python 3.11 or newer is required.

### Removed

- Aboveground biomass and carbon, moved to the v2.0 roadmap.
- The internal Portuguese documentation files (technical notes, roadmap and installer guide), replaced by the English documents in `docs/` and the README.

### Known limitations

- Internal identifiers in the interface layer (some variable and function names in the chart, report and page modules) are still partly in Portuguese. They are not shown to users and will be translated in a later release.
