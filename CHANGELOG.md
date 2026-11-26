# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.3.0] - 2026-11-26

### Added

- Manual on the documentation site in Portuguese and English (10 pages each: what the app is for, opening it, building the spreadsheet, sidebar and settings, single plot, multiple plots, temporal, colonization, export and use of the results, troubleshooting), illustrated with screenshots of the app (`docs/images/manual/`).

### Changed

- Documentation site with the MangueTREE look: app logo and favicon, the same green palette and font as the app (`docs/stylesheets/manguetree.css`).
- Saved files now have organised names: `<plot>[_<year>]_<what>.<ext>`, with no accents or spaces (for example `H2_Height-and-profile.png`, `H2_Tables.xlsx`, `H2_Report.pdf`, `H2_Figures.zip`). This covers the camera button of every chart, the chart tables, the tables and PDF of each page, the summary panel and the ZIP of figures; several plots list the plots (`F2-H2-J2_...`) and the temporal analysis adds the years (`H2_2003-2025_...`).

## [1.2.0] - 2026-11-24

### Changed (home and colonization layout)

- Home page: the data template (download buttons) comes before "Choose an analysis", with "How to format your data" inside the same box.
- Colonization page: the Charts tab comes first and holds the sub-tabs Density, Height, Age, Crossing, Count by cohort and Jiménez schematic; the density and height tables now sit under their charts; then Check and Export. Each chart has its choices in one row with the Adjust and Chart table buttons, as in the structure pages.
- Colonization, Age: both axes with the same size (square plot), age from 0 to 10 years, density with complete numbers (10.000), linear or log; chart types points, points with SD, line, columns, columns with SD and horizontal bars; optional fitted curve with its equation.
- Colonization, Crossing: "X vs Y" renamed scatter plot, with the least-squares line and, below it, the equation, Pearson r, p, R² and n, which follow the X axis chosen.
- Colonization, Count by cohort: colours can be default (as before), a ready-made palette, a gradient of one colour or each colour picked.
- Colonization, Jiménez schematic: explanatory texts under the charts removed (the figure of the article has no equation).
- Colonization, Height: same chart types as the Age tab (line, points, columns, horizontal bars, and the versions with standard deviation; default line with SD).
- Colonization, Age: types without standard deviation (one value per plot and age); the fitted curve switch, the fit and the equations moved to the right of the chart.
- Colonization, Jiménez schematic: both charts share the same margins, so their axes start and end at the same heights.
- Colonization, Height: standard deviation drawn upwards only, columns start at the axis without an empty band, chart title is just "Height".
- Colonization, Density: same chart types as Height (line, points, columns, horizontal bars).
- Colonization, Age: legend inside the chart (upper left), points at the edge no longer cut.
- Colonization, joined plots: the legend of the joined years goes in one row below the chart, so it no longer squeezes the plotting area.
- Colonization, Jiménez schematic: no Adjust and Table buttons on the two charts.

### Changed (latest round)

- Species always appear in the same fixed order in every chart, legend, table and menu of the app (Rhizophora, Avicennia, Laguncularia, Conocarpus, then others, unidentified last), and keep the same colours across charts.
- Temporal page, Evolution and Mortality tabs: one row above the charts holds the chart type, gaps, a single "Adjust charts" menu (axis limits of each chart separately, plus size and bar width) and a single "Chart tables" menu to download the tables of the charts below, replacing the per-chart buttons.
- Notes under the temporal charts (points are plot values per year; stems without DBH are left out of density and basal area) now sit after the charts with spacing so they never overlap a figure.

### Changed

- License changed from MIT to GPL-3.0-or-later (agreed by all authors). Versions up to 1.1.0 remain available under the MIT license. License notice added to the source files and to the About page.

### Added

- PDF report redesigned as a scientific article (single plot, multiple plots, temporal): cover with logo on a transparent background, key numbers and summary text, numbered headings, numbered figure and table captions, summary panel, panels of charts with letters (a, b, c) and spacing, map of the plots when latitude and longitude exist, and the data check at the end. The text uses the full page width and flows from the first page to the next.
- PDF report uses the app's own charts as they are on screen (same options, texts and colours) grouped by tab, when Chrome or Chromium is installed (kaleido); otherwise the charts are redrawn automatically. The PDF is now prepared on demand with a Prepare PDF button and flagged as out of date when the charts or settings change.
- Colonization dynamics page: reads the NEMA colonization workbooks (one per plot), identifies the collections and the year of each, standardises the codes and shows a check (collections and years with manual correction, codes and their classes, juveniles by cohort, repeated tags, ignored notes) before any result. Then it computes the density of juveniles (ind/ha), with only the individuals with a cohort or including those without, by species, with plots A and B joined (counts and areas added) and a CSV download.
- Colonization page: juvenile height (mean, sample SD, n, optional minimum of 100 cm), relative density by species and a Charts tab (density curve per plot with log option, species composition per plot, height mean with SD), using the app palettes and style controls.
- Colonization page: clean export (long and wide, CSV and Excel), reclassification of codes by the user, plot age with a log-linear fit of density against age, and a schematic of stem density over stand development (Jiménez et al. 1985, Fig. 2) next to the observed density.
- Theoretical curve of Jiménez, Lugo and Cintrón (1985) for live stem density against mean DBH, drawn under the plots of the single plot, multiple plots and temporal pages (`calc.jimenez_density_ha`, `charts.fig_jimenez`); reference values of the same paper in the colonization charts; Jiménez et al. (1985) and Cavalcanti et al. (2009) added to the references (docs/methods.md, About page).
- Colonization page, second round: more on the check screen (codes per year, records per collection, species, height alerts); count of individuals per year by class or by code, joining selections and stacked by cohort, species or item (new Count by cohort chart); height by any class, not only juveniles; free joining of plots (up to three groups) applied to every tab; charts grouped in sub-tabs (density, age, height, count, Jiménez schematic); sidebar form with a Run analysis button; Excel prepared on demand.
- Every chart of the app can have its texts edited (title, axis titles, labels) in the Adjust menu.
- Module `manguetree.colonizacao` (reader and density) and tests, including a validation against the published density table of the monograph (98 of 100 values equal; the 2 others are a typing error of the table).
- PDF reports rebuilt in one visual identity for the four modes (single plot, multiple plots, temporal, colonization): always A4 portrait, cover with key numbers and a reading of the results, tables with proportional bars, grouped data check, numbered pages ("Page X of Y"), bundled Liberation Sans font (SIL OFL), decimal comma in Portuguese on tables and chart axes, and a fixed species palette (same colour for a species in every chart). In multiple-plot reports each plot keeps one colour across all charts.
- Plot-location map (app and PDF report): the same figure, with satellite imagery (Esri World Imagery, downloaded when the map is drawn; the plain coordinate plot is used offline) and a small pin on each plot.
- Box and violin plots have a thin outline in the axis colour, in the app and in the PDF report.
- Colonization page, joined plots: a year in which one plot of a union was not sampled (for example H+I in 2016-2018) is marked as incomplete, with an asterisk and an open diamond in the charts, a warning under tables and charts, and the columns `membros`, `n_parcelas` and `incompleta` in the tables; an option hides those years. The calculation (sum of juveniles over the sum of the areas, not the mean of the densities) is documented in `docs/methods.md`.
- Heights in metres or centimetres (sidebar choice) on every page: tables, charts, exports, summary panel and PDF report (`manguetree.unidades`).
- Results in tables, labels and exports with two decimals (0,00 / 0.00); axes keep the complete numbers.
- Table of every chart (Excel, CSV or TXT), next to the save-as-picture button, and the three formats in every export (`manguetree.exportar`): organised Excel, CSV for Excel (semicolon and decimal comma in Portuguese; UTF-8 with BOM) and tab-separated TXT. The data template also comes as TXT.
- Colonization: in years with more than one collection the Height tab shows mean, SD and N of each collection and uses by default the one with most heights (or the last, or one chosen per plot and year).
- Colonization: Crossing tab (Charts) with juvenile height against density, as lines over the years or X vs Y, with the Pearson correlation per plot.
- Cleaner layout: Adjust and Chart table are two small buttons in one row above each chart; chart type and parameters of multiple plots, species by plot and temporal species are collapsing menus in one row; export columns aligned, with bold titles and no icons; explanation under the charts that use formulas (IVI, comparative profile, species by plot, time series).
- Citations: the NEMA/UERJ thesis of Estrada (2013) is replaced by Estrada et al. (2013, Aquatic Botany 111:135-143) in the app, reports and documentation.
- The Jiménez curve note no longer interprets densities below the curve; the comparative profile is named and explained as a radar chart with normalised values.
- Structure always in stems per hectare (the stems-per-plot selector is gone; the live-density card shows the number of stems in the plot under its value).
- Each chart's own choices (type, metric, 100%, profile kind, species, log scale) sit in one row with Adjust and Chart table; in the temporal evolution and mortality charts the two buttons are icons in the chart's corner, next to the camera and zoom icons.
- Temporal evolution: more chart types (line, points, columns, horizontal bars, and line, points or columns with standard deviation for mean height).
- Explanations under the charts of the single-plot page (height-DBH, vertical profile, DBH classes, histogram, composition) and the radar chart equation.
- Wording: the field protocol is cited as the protocol of the Mangrove Study Group of UERJ (NEMA/UERJ), not as a spreadsheet.
- The colonization page is a preview: hidden in the menu and blocked unless the environment variable `MANGUETREE_COLONIZACAO=1` (or the app secret `colonizacao = true`) is set.

## [1.1.0] - 2026-11-18

Large update made with the NEMA/UERJ laboratory. Laiza Lacerda Motta joins the authors.

### Added

- Interface opens in Portuguese, with a flag selector (Portuguese / English) and a translated page menu.
- MangueTREE icon set (drawn from the logo) in the menu, tabs and headings, in place of emoji.
- Data check moved to its own tab (before Export) on every analysis page, with a one-line summary above the tabs.
- Single plot: interactive summary panel (values on hover; light or dark; PNG or PDF download); vertical profile as circles (default, with a size legend), stems, strata or distribution by species; species selection for the height × DBH regression with the equations beside the chart; RD%, RDo%, RF% and IVI explained under the table; 100% option for DBH classes and phytosociology; share (%) next to each value in the table by genus.
- Multiple plots: free chart (box plot, violin, columns or line; dual axis with line or markers; X × Y) opening on DBH; explanation of the normalised profile; share of each species (live and dead) in the parameter table; species chart with stacked or 100% columns and dead part hatched.
- Temporal: several workbooks (one per plot) analysed together, one line per plot or mean ± SD; every plot parameter (DBH, heights, live, dead and total density and basal area, counts, mortality in stems and basal area, Holdridge, richness, each DBH class, stems without DBH); every species parameter (density and basal area live, dead and total, shares, DBH, heights, RD, RDo); live + dead by species with the dead part hatched; plots side by side, one species with the plots side by side, and the difference between two plots; title above the tables saying what they show; columns side by side for years without a survey (option to keep the gaps).
- Chart settings for the page (fonts, bar width, height, full or fixed width) and an Adjust menu on each chart (height, width, bar width, Y limits); a fixed width is kept in the saved PNG.
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
- Summary panel and figure export use `st.iframe`, the current Streamlit API (the deprecated `st.components.v1.html` is no longer used).

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
