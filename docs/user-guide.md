# User guide

This guide describes the MangueTREE app (version 1.2.0). For the engine as a library, see the Quick start in the [README](https://github.com/luq317/MangueTREE/blob/main/README.md). The formulas are in [methods.md](methods.md) and the file layout in [data-format.md](data-format.md).

## Starting the app

Desktop builds start with a double-click; see the Download section of the [README](https://github.com/luq317/MangueTREE/blob/main/README.md). From the source code, run `manguetree` (or `streamlit run src/manguetree/app/Home.py`) and open `http://localhost:8501` if the browser does not open by itself.

The app opens in Portuguese. The language selector (flag) at the top of the sidebar switches to English; the choice is kept between pages and applies to tables, figures and exports. Below it, the page menu (Home, Single plot, Multiple plots, Temporal, About).

The home page offers, before the choice of analysis, a **data template** (with "How to format your data" inside the same box) (Portuguese or English headers; Excel with an instructions sheet and the species codes, or CSV).

## Settings shared by the analysis pages

- **Region.** Selects the species expected in your plots and how genus abbreviations are resolved. `Av` is always *Avicennia schaueriana* (write `Ag` for *A. germinans*); `Rh` is *Rhizophora mangle* in Brazil South and Southeast.
- **Species table.** An expander shows the table of species and aliases. You can edit it, add species, upload your own CSV with the same columns, or reset it.
- **DBH class cutoffs.** Two cutoffs in cm (2.5 and 10 by default) that define three classes and the two Holdridge indices.
- **Plot area.** Read from the file when possible. The default area (100 m²) is used only when the file has none, and the data check warns when that happens.
- **Style.** Colour palette (MangueTREE keeps a colour per species; Lab and Greens recolour the species), the MangueTREE seal (lower right corner, outside the chart) and **Chart settings**: title and axis font, bar width, chart height and width (full width or a fixed width in pixels) for every chart of the page.
- **Adjust (on each chart).** Height, width, bar width and Y axis limits of that chart only. A fixed width is also the width of the saved PNG.
- **Figures of the open tab.** Saves every chart of the open tab as PNG, in one ZIP, at the chosen resolution (150 to 600 DPI). The camera icon of each chart saves that chart alone.

## Data check

A line above the tabs gives the number of errors and warnings. The **Data check** tab (before Export) lists every issue with the spreadsheet row, a description and the action taken. When stems have a DBH and no condition, the tab asks whether to exclude them (default), count them as live or as dead. See [data-format.md](data-format.md#validation).

## Single plot

Upload an `.xlsx`, `.csv` or `.txt` file; with several sheets, pick the sheet (one plot).

- **Summary panel.** One view of the plot: mean DBH with the DBH classes, height (mean ± SD and canopy), live density with the share of each species, total basal area (live solid, dead hatched, by species), mortality in stems and in basal area, Holdridge index. Hovering shows the values. Light or dark theme; download as PNG (chosen DPI) or PDF.
- **Structure.** Cards in the order DBH, mean height ± SD, canopy height, live density, live basal area, then total basal area, mortality, stems per tree, Holdridge indices and number of species. Density as stems per hectare or number of stems. Table by genus with the share (%) next to each value.
- **Phytosociology.** Relative density (RD%), relative dominance (RDo%) and, with several plots, relative frequency (RF%) and IVI, with the definitions under the table; option to show each value as a 100% column split by species. Basal area composition.
- **DBH classes.** Density or basal area by class and species, absolute or 100%; histogram; regular classes with De Liocourt's quotient.
- **Height and profile.** Height × DBH with a linear regression per species; choose the species and read the equations beside the chart. Vertical profile as circles (size = DBH, with a size legend), stems, strata by height class or distribution by species.
- **Map, Data check, Export** (PDF report with the data check at the end, Excel, CSV).

## Multiple plots

Upload an Excel file with one sheet per plot, fill the sidebar form and click run.

- **Comparison.** Normalised profile of the plots (each parameter divided by its maximum), then a free chart: one parameter (box plot or violin of the stems for DBH and height, columns or line for the others), dual axis (second axis as line with markers or markers only) or X × Y. Table of parameters per plot in the lab order, with the share of each species (live and dead) in density or basal area.
- **Species per plot.** Contribution of each species per plot, live solid and dead hatched, stacked or 100%, in basal area or density (per hectare or number of stems).
- **IVI (all plots)**, with the plots as sampling units. **Map, Data check, Export.**

## Temporal analysis

Upload one Excel file per plot, each sheet one survey (year). The year comes from the sheet name; years not found must be typed, and all of them can be checked in "Check the years of the sheets".

- **Evolution.** Any plot parameter over the years (DBH, heights, live, dead and total density and basal area, counts, mortality, Holdridge, richness, each DBH class, stems without DBH), as lines or columns, in separate charts or on two axes. With several plots: one line per plot or mean ± SD.
  In Evolution and Mortality, one row above the charts has the chart type, gaps, **Adjust charts** (axis limits of each chart separately, size and bar width) and **Chart tables** (pick which tables to download), so there are no per-chart buttons. Species always follow the same order in every chart: Rhizophora, Avicennia, Laguncularia, Conocarpus, others, unidentified last.
- **By species.** Any species parameter (density and basal area live, dead and total, shares, DBH, heights, RD, RDo), opening on live + dead basal area (dead hatched). Lines, columns, stacked or 100% stacked, with optional values. With several plots: plots side by side, one species with the plots side by side, the difference between two plots, the mean, or one plot. The table under the chart shows the same data and says which.
- **Mortality.** Mortality in stems and in basal area, live and dead by species, and the number of stems without DBH in each year.
- **Full series, Data check, Export.**
- Years without a survey: columns are placed side by side by default; "Leave space for years without a survey" puts the gaps back.

## Units, decimals and saved tables

- **Height unit.** Choose metres or centimetres in the sidebar; it applies to tables, charts, exports and the PDF report of every page.
- **Two decimals.** Results in tables, labels and exports have two decimals (0,00 in Portuguese, 0.00 in English); counts stay whole. Chart axes show the complete numbers.
- **Layout.** Above each chart, two small buttons (Adjust and Chart table) sit on the right. Chart type, metric and condition are menus that collapse, side by side; options such as showing values sit just below them.
- **Save the table of a chart.** Next to the save-as-picture button, each chart has a **Chart table** menu: Excel, CSV or TXT with the data of that chart.
- **Excel, CSV or TXT.** Every export offers the three formats. The CSV opens directly in Excel (Portuguese: `;` and decimal comma; English: `,` and point); if columns look glued together in another program, use the Excel file or the TXT (tab-separated).
- **Colonization, height by collection.** In years with more than one collection, the Height tab shows the mean, SD and N of each one and which is used (by default the one with most heights); open **Collections of each year** to choose another. The Crossing tab in Charts draws height with density, as lines or X vs Y.

## Reading the results

- Per-hectare values are scaled from the plot area, so a wrong area changes every value.
- A single plot has no frequency. Use several plots for the IVI.
- Stems whose species could not be resolved count in density and basal area but not in richness or IVI.
- Heights come from live stems only. Canopy height is the mean of the 10 tallest live heights ([methods.md](methods.md#6-decisions-and-adaptations)).
- Stems without DBH are left out of density and basal area ([methods.md](methods.md#8-values-added-in-version-110)).

## Troubleshooting

- *Header not found.* The sheet must have a row with tree identifier, species, DBH and condition within its first 25 rows; compare with the data template.
- *Many unknown species.* Check the region, or add the aliases you use to the species table.
- *Area warning.* Add an area label and value to the sheet header, or give the area cell in the sidebar.
- *A change does not show up (running from source).* Install the package in editable mode (`pip install -e .`) and restart the app.
