# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-11-18

Large update made with the NEMA/UERJ laboratory. Laiza Lacerda Motta joins the authors.

### Added

- Interface opens in Portuguese, with a flag selector (Portuguese / English) and a translated page menu.
- MangueTREE icon set (drawn from the logo) in the menu, tabs and headings, in place of emoji.
- Data check moved to its own tab (before Export) on every analysis page, with a one-line summary above the tabs.
- Single plot: interactive summary panel (values on hover; light or dark; PNG or PDF download); vertical profile as circles (default, with a size legend), stems, strata or distribution by species; species selection for the height × DBH regression with the equations beside the chart; RD%, RDo%, RF% and IVI explained under the table; 100% option for DBH classes and phytosociology; share (%) next to each value in the table by genus.
- Multiple plots: free chart (box plot, violin, columns or line; dual axis with line or markers; X × Y) opening on DBH; explanation of the normalised profile; share of each species (live and dead) in the parameter table; species chart with stacked or 100% columns and dead part hatched.
- Temporal: several workbooks (one per plot) analysed together, one line per plot or mean ± SD; every plot parameter (DBH, heights, live, dead and total density and basal area, counts, mortality in stems and basal area, Holdridge, richness, each DBH class, stems without DBH); every species parameter (density and basal area live, dead and total, shares, DBH, heights, RD, RDo); live + dead by species with the dead part hatched; plots side by side, one species with the plots side by side, and the difference between two plots; title above the tables saying what they show; columns side by side for years without a survey (option to keep the gaps).
- Chart settings for the page (fonts, bar width, height) and an Adjust menu on each chart (height, bar width, Y limits).
- Every figure of the open tab as PNG in one ZIP, at 150 to 600 DPI.
- Data template on the home page (Portuguese or English; Excel with instructions and species codes, or CSV).
- Densities as stems per hectare or number of stems in the plot.
- Palettes MangueTREE (one colour per species), Lab (navy, teal, greys) and Greens; the chosen palette now recolours the species charts.
- Download section in the README with direct links to the Windows and macOS builds; release notes taken from this changelog.

### Changed

- Parameters in the lab order (DBH, mean height, canopy height, live density, live basal area, species shares, number of species last) in cards, tables and selectors.
- Structure cards smaller and of equal size; the height SD on the value line.
- PDF reports start with the results; the data check closes the report.
- MangueTREE seal in the lower right corner, outside the plotting area.
- Selector titles in bold.

### Fixed

- `Av` is read as *Avicennia schaueriana* in every region, the convention of the NEMA/UERJ field sheets (`AV`, `RH`, `LG`); in 1.0.0 it was an ambiguous species and those stems left richness and the importance values. *A. germinans* is written `Ag`.
- Chart axes show full numbers with thousands separators (10.000 / 10,000), never 10k; decimal separator follows the language.
- Test of `requirements.txt` accepts the `.` line used by Streamlit Community Cloud (the GitHub tests failed since that change).

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
