# What MangueTREE is for

MangueTREE reads the field spreadsheet of a mangrove plot and calculates, in seconds, the structural and phytosociological parameters that are usually done by hand in spreadsheets. It was created at the Mangrove Studies Group of UERJ (NEMA/UERJ) and follows the group's protocol, but accepts spreadsheets from other groups as long as they have the basic columns.

## What it calculates

- **Structure:** density (stems per hectare), basal area, mean DBH, mean height and canopy height, number of species, mortality in stems and in basal area, stems per tree.
- **Phytosociology:** relative density (RD%), relative dominance (RDo%), relative frequency (RF%, with several plots) and importance value (IVI).
- **DBH classes:** density and basal area by class, histogram and De Liocourt's quotient.
- **Complexity:** Holdridge complexity index.
- **Height:** height × DBH relation by species and the vertical profile of the plot.
- **Several plots:** comparison between plots and IVI with the plots as sampling units.
- **Several years:** evolution of any parameter, by species, and mortality over time.
- **Colonization:** density and height of juveniles, plot age, height × density crossing and count by cohort (preview).

Formulas, conventions and sources are on the [Methods](../methods.md) page.

## What it does not do

- It does not correct the spreadsheet: it warns about what looks wrong (**Data check** tab) but does not change values by itself.
- It does not replace a critical reading of the results. A per-hectare value changes if the plot area is wrong, for example.
- With a single plot there is no relative frequency or full IVI. For the IVI, use [Multiple plots](06-multiple-plots.md).

## Where your data stay

The app runs on your computer. In the Windows and macOS version, no data leaves your machine and no internet is needed, not even for the PDF report.

## How to cite

Pereira LS, Motta LL, Matta TC, Chaves FO, Soares MLG (2026). MangueTREE v1.3.1. https://github.com/luq317/MangueTREE. The home page of the app and the [README](https://github.com/luq317/MangueTREE/blob/main/README.md) have the full citation and the BibTeX. The calculations are based on Cintrón and Schaeffer-Novelli, Pool et al. and Estrada et al. (2013, Aquatic Botany 111:135-143).
