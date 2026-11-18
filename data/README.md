# Example data: Guaratiba mangrove, Rio de Janeiro, Brazil

These files are the example data shipped with MangueTREE. They are used by the
test suite, which compares the engine against the laboratory spreadsheet, and
they can be uploaded to the app to try every analysis page.

## Provenance

- Site: Guaratiba mangrove, Rio de Janeiro, Brazil.
- Source: Núcleo de Estudos em Manguezais (NEMA), Universidade do Estado do Rio
  de Janeiro (UERJ). The data come from permanent plots of transect T2.
- Plots: F2 (fringe), H2 (basin) and J2 (transition).
- `guaratiba_T2_2009.xlsx`: the three plots (F2, H2, J2) surveyed in 2009, one
  sheet per plot.
- `guaratiba_H2_2003_2025.xlsx`: plot H2 surveyed 15 times between 2003 and 2025,
  one sheet per survey (the sheet name is the survey year).
- `guaratiba_F2_with_errors.xlsx`: plot F2 (2009) with deliberate mistakes (an unknown species, an implausible DBH, a stem without condition, a dead stem with a height, a tag repeated with another species). It is used to demonstrate the data check and is not a real survey.
- The published files use the MangueTREE species codes. The laboratory spreadsheets use genus abbreviations, which were mapped when the files were converted: Av to As (*Avicennia schaueriana*) and Rh to Rm (*Rhizophora mangle*); Lg (*Laguncularia racemosa*) is already a species code. Guaratiba has only these three species.
- The files were converted from the laboratory spreadsheets into the MangueTREE
  layout. Tag numbers and field notes were removed.
- Published with the permission of NEMA.

## How to cite

Please cite the MangueTREE software (see the main README) and Pereira LS, Matta TC,
Chaves FO, Soares MLG. Influence of environmental gradient on mangrove litterfall production: a
long-term study in southeastern Brazil (manuscript under review).

## Sheet layout

Each sheet starts with a few header lines (site, plot, year, plot area) and then
the table of stems, one row per stem.

| Column | Description |
| --- | --- |
| `site` | Header line: site name. |
| `plot` | Header line: plot code (F2, H2 or J2). |
| `year` | Header line: survey year. |
| `plot_area_m2` | Header line: plot area in square metres. |
| `tree_id` | Tree identifier. Repeated for the stems of the same tree. |
| `n_stems` | Number of stems of the tree. |
| `species` | Species as written in the field sheet (species code: As, Rm or Lg). |
| `dbh_cm` | Diameter at breast height, in cm. |
| `height_m` | Tree height, in m (usually recorded on the first stem of each tree). |
| `condition` | `v` for a live stem, `m` for a dead stem. |
