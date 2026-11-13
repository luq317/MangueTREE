# Data format

MangueTREE reads field tables with one row per stem. This page describes the accepted files, columns, conventions and the validation checks.

## Files

- **Excel (`.xlsx`).** One sheet per plot (multiple-plot analysis) or one sheet per survey (temporal analysis). The single-plot page reads one sheet at a time; with several sheets, you choose which one.
- **CSV or TXT.** One plot per file, header on the first line, `;` as the default delimiter (you can change it in the app). UTF-8 and Windows-1252 encodings are accepted. A CSV file has no header lines, so the plot area is given in the app.

The example files in `data/` show the layout; see [data/README.md](../data/README.md).

## Sheet layout

A sheet may start with a few header lines (site, plot, year, plot area) followed by the table of stems. MangueTREE scans the first 25 rows and takes as header the first row that contains all required columns. Data start on the next row, and blank rows are ignored.

## Columns

| Column | Required | Description | Accepted names (examples) |
| --- | --- | --- | --- |
| Tree identifier | yes | Identifier of the tree. Repeat it for each stem of the same tree. | `tree_id`, `tree`, `ind`, `individuo`, `arvore` |
| Species | yes | Scientific name, code, alias or genus abbreviation. | `species`, `spp`, `especie`, `sp` |
| DBH | yes | Diameter at breast height in cm, per stem. | `dbh_cm`, `dbh`, `dap`, `diametro` |
| Condition | yes | `v` live, `m` dead. | `condition`, `cond`, `condicao` |
| Number of stems | no | Declared number of stems of the tree, used for a consistency check. | `n_stems`, `stems`, `n troncos` |
| Height | no | Tree height in m, usually on the first stem of the tree. | `height_m`, `height`, `altura` |
| Latitude, longitude | no | Coordinates. | `lat`, `latitude`, `lon`, `long`, `longitude` |
| Tag | no | Field tag, used to detect repeated tags. | `tag`, `lacre` |
| Note | no | Free text. | `note`, `obs`, `observacao` |

Column names are matched ignoring case and accents; dots and apostrophes are removed, underscores become spaces, and units in brackets or parentheses are dropped (so `DAP (cm)` matches `dap`). An exact match of the cleaned name is tried first. For columns still unmatched, longer aliases (4 or more letters) match when contained in the header, and shorter aliases match the first word of the header (`dap cm` gives `dap`, and `lon gps` gives `lon`, but `xlon` does not). English and Portuguese names are both recognised. The full list of aliases is in `COLUMN_ALIASES` in `src/manguetree/io.py`.

Values may use a decimal comma (`12,6`). A blank cell is a missing value. A DBH or height cell that holds text that is not a number is treated as missing and reported by the validation.

### Condition codes

Live: `v`, `vivo`, `viva`, `live`, `alive`, `l`. Dead: `m`, `morto`, `morta`, `dead`, `d`. Case, accents and trailing punctuation are ignored. A blank condition on a stem with DBH is an error; by default the stem is excluded, and the app lets you count such stems as live or dead. An unrecognised code is an error and the stem is excluded.

### Species

Species are resolved against the species table of the selected region (see [Species table](#species-table)). A cell may contain:

- the scientific name (`Rhizophora mangle`),
- the code (`Rm`) or an alias (`mangue vermelho`),
- a genus abbreviation (`Rh`, `Av`, `Lg`, `Cn`, `Pe`), resolved with the regional default when one is justified. The abbreviation resolves only where the region has a single species of the genus: `Lg` is *Laguncularia racemosa* and `Cn`, `Ce` and `Co` are *Conocarpus erectus* in every region, and `Rh` is *Rhizophora mangle* in Brazil South and Southeast only. `Av` is ambiguous in all four regions, `Rh` is ambiguous in the other three regions, and `Pe` is ambiguous in the Caribbean and the Eastern Pacific. Use the species code (`As`, `Ag`, ...) or add an alias in the species table to resolve them.

Species that cannot be resolved are reported by the validation and are not counted as a species; see [methods](methods.md#6-decisions-and-adaptations).

## Plot area

The plot area (m²) is looked for in this order:

1. a number in the cell to the right of an area label in the header lines (`plot_area_m2`, `Plot area`, `Área`, `Área da parcela`, `Parcela (m2)`, and similar),
2. a cell that you specify (for example `B4`),
3. the default area you set in the app (100 m² if you do not change it).

When the third option is used, the validation reports `area_fallback`. Check this warning, because the area scales every per-hectare value.

## Species table

The table is `src/manguetree/data/species_neotropics.csv`, with the columns `code`, `scientific_name`, `genus`, `aliases` (separated by `|`), `regions` (separated by `|`), `true_mangrove` (`true` or `false`) and `source`. It lists ten taxa, each with one unique two-letter code (case-insensitive): `Rm` *Rhizophora mangle*, `Rr` *R. racemosa*, `Rx` *R. x harrisonii*, `Ag` *Avicennia germinans*, `As` *A. schaueriana*, `Ab` *A. bicolor*, `Lg` *Laguncularia racemosa*, `Ce` *Conocarpus erectus* (a mangrove associate, `true_mangrove` false), `Pr` *Pelliciera rhizophorae* and `Pb` *P. benthamii* (split by Duke 2020). `Lg` keeps the laboratory abbreviation, and the hybrid is `Rx` because `Rh` stays the genus abbreviation of *Rhizophora* (see below). The regions are `BR_S_SE`, `BR_N_NE`, `CARIBBEAN_ATLANTIC` and `EASTERN_PACIFIC`. Regional defaults for genus abbreviations are in `genus_defaults.csv`.

The species and region table is provisional and awaits review by regional experts. In the app you can edit the table, upload your own CSV with the same columns, and add aliases. A user alias takes priority over the regional genus defaults.

## Validation

`manguetree.validation.validate` returns the list of issues, errors first and then by row. Each issue has a kind, a severity (`error` or `warning`), the row in the original file, the tree identifier, a description and the action taken. The app shows the list in a data-check panel and includes it in the Excel and PDF exports.

| Kind | Severity | Meaning | Action |
| --- | --- | --- | --- |
| `non_numeric_value` | error | DBH or height cell holds text that is not a number. | Stem excluded (DBH) or height excluded. |
| `implausible_value` | error | DBH or height is zero or negative. | Stem excluded (DBH) or height excluded. |
| `implausible_value` | warning | DBH above 150 cm or height above 60 m (default limits). | None. Check the value. |
| `dbh_without_condition` | error | DBH with no condition. | Excluded unless you choose live or dead. |
| `unknown_condition` | error | Condition code not recognised. | Stem excluded. |
| `condition_without_dbh` | warning | Condition with no DBH. | Excluded from density and basal area. |
| `unknown_species` | error | Species text not found in the table. | Counted in totals; excluded from richness and from the phytosociology table. |
| `ambiguous_species` | error | Genus abbreviation with no regional default. | Counted in totals; excluded from richness and from the phytosociology table. |
| `tree_species_conflict` | warning | Stems of one tree have different species. | None. |
| `stem_count_mismatch` | warning | Declared number of stems differs from the rows found. | None. |
| `tree_without_stems` | warning | Tree listed with no measured stem. | None. |
| `duplicate_tag` | warning | Same tag on more than one row. | None. |
| `dead_with_height` | warning | Dead stem with a recorded height. | Height ignored. |
| `ambiguous_height_column` | warning | Height read from a column named `alt med`, which may be observer eye height. | None. Check the column. |
| `area_fallback` | warning | Plot area not found in the file. | Fallback area used. |
| `duplicate_year` | warning | Same year given to more than one sheet (temporal analysis). | Values averaged. |

## Example

```text
site      Guaratiba
plot      F2
year      2009
plot_area_m2   225

tree_id  n_stems  species  dbh_cm  height_m  condition
1        1        Rm      4.8     5.2       v
2        2        As      12.1    8.0       v
2        2        Av       3.0               v
3        1        Lg      2.2               m
```
