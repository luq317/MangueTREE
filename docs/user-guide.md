# User guide

This guide describes the MangueTREE app. For the engine as a library, see the Quick start in the [README](../README.md). The formulas are in [methods.md](methods.md) and the file layout in [data-format.md](data-format.md).

## Starting the app

Run `manguetree` (or `streamlit run src/manguetree/app/Home.py`) and open `http://localhost:8501` if the browser does not open by itself. Desktop builds start with a double-click; see [installers.md](installers.md).

The sidebar of every page starts with the language selector (English or Portuguese). The choice is kept when you move between pages and applies to tables, figures and exports.

## Settings shared by the analysis pages

- **Region.** Selects the species expected in your plots and how genus abbreviations such as `Rh` are resolved (`Av` is ambiguous everywhere; use the species code, e.g. `As` or `Ag`). Choose the region of your site: Brazil South and Southeast, Brazil North and Northeast, Caribbean and Western Atlantic, or Eastern Pacific (Americas).
- **Species table.** An expander shows the table of species and aliases. You can edit it, add species, upload your own CSV with the same columns, or reset it. The table is provisional; check it against your regional flora.
- **DBH class cutoffs.** Two cutoffs in cm (2.5 and 10 by default) that define three classes. The cutoffs must differ.
- **Plot area.** The area is read from the file when possible. The default or fallback area (100 m²) is used only when the file has none; the data-check panel warns you when that happens. A `.csv` or `.txt` file never carries the area, so for those files the warning stays until you change the area in the sidebar from its default value.
- **Style.** Colour palette and, on the single-plot page, font sizes. An option adds the MangueTREE seal to figures and PDF reports.

## Data-check panel

After you load a file, the data-check panel lists the issues found, with the spreadsheet row, a description and the action taken. Read it before the results. When stems have a DBH and a blank condition, the panel asks whether to exclude them (the default), count them as live, or count them as dead. See [data-format.md](data-format.md#validation) for every check.

## Single plot

Upload an `.xlsx`, `.csv` or `.txt` file. When an Excel workbook has several sheets, pick the sheet (one plot) in the sidebar; its name becomes the plot name in the titles, the PDF and the exports. For CSV or TXT, set the delimiter (`;` by default). Set the plot area (always for CSV or TXT; for Excel, when the sheet does not carry it), or give the cell that holds it (for example `B4`).

The page shows:

- the structural parameters (live density and basal area, mean DBH, mean and canopy height, stems per tree, mortality, Holdridge indices) on the Structure tab, and the full summary table in the exports (PDF and Excel), which adds dead and total density and basal area and the minimum and maximum height;
- the per-species table, with relative density, relative dominance (and relative frequency and the IVI when several plots are analysed together);
- density and basal area by DBH class and species, with the cutoffs you set;
- the diameter distribution in regular classes (width configurable) with De Liocourt's quotient $q$, reported without interpretation;
- the Holdridge complexity index for DBH > 2.5 cm and DBH > 10 cm;
- charts of species composition by basal area (pie or treemap), DBH classes by density or basal area, and height.

Exports: PDF report, Excel tables (summary, per species, DBH classes, data, issues) and a per-species CSV.

## Multiple plots

Upload an Excel file with one sheet per plot. Fill the form in the sidebar (area cell, default area, cutoffs, plots to analyse) and click run. The plot name is the sheet name.

The page compares the plots on any structural metric, shows species composition per plot, and computes the IVI with the plots as sampling units (frequency is the share of plots where the species occurs). Sheets with no usable data are listed and skipped.

Exports: PDF report, Excel (one sheet per plot) and CSV of the comparison and of the species data.

## Temporal analysis

Upload an Excel file with one sheet per survey of the same plot. The year of each sheet is detected from its name; confirm or correct it. If two sheets receive the same year, the data-check panel reports `duplicate_year` and the values for that year are averaged, both in the series of the whole plot and in the per-species series.

The page plots the structural parameters over the years, in separate panels or on two axes, and the per-species series (as lines or areas) for the metric you choose.

Exports: PDF report, Excel (including the per-species series) and CSV.

## Reading the results

- Per-hectare values are scaled from the plot area, so a wrong area changes every value.
- A single plot has no frequency. Use several plots for the IVI.
- Stems whose species could not be resolved count in density and basal area but not in richness or IVI. They appear as "Unidentified" in the DBH-class tables and the composition charts, and are not listed in the phytosociology table, which holds identified species only.
- Heights come from live stems only. Canopy height is the mean of the 10 tallest live heights, which is an adaptation described in [methods.md](methods.md#6-decisions-and-adaptations).

## Troubleshooting

- *Header not found.* The sheet must have a row that holds tree identifier, species, DBH and condition columns within its first 25 rows. Check the column names against [data-format.md](data-format.md#columns).
- *Many unknown species.* Check the region, or add the aliases you use to the species table.
- *Area warning.* Add an area label and value to the sheet header, or give the area cell in the sidebar.
- *PDF unavailable.* The app shows the reason in place of the download button; the Excel and CSV exports still work.
