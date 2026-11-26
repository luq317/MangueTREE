# Colonization

This page studies regeneration (juveniles) with the NEMA/UERJ colonization spreadsheets, one per plot. It is a **preview**: it stays hidden in the menu until it is enabled.

## How to enable

In a terminal, inside the project folder:

```
PYTHONPATH=src MANGUETREE_COLONIZACAO=1 streamlit run src/manguetree/app/Home.py
```

On Streamlit Cloud, create the secret `colonizacao = true` in the app settings.

## How to upload the spreadsheets

Upload one `.xlsx` per plot and click **Run analysis** in the sidebar. The app identifies the collections and the year of each, standardises the codes and shows a check. You can correct a year and reclassify codes.

## The tabs

**Charts**, with the sub-tabs:

- **Density:** curve of juvenile density per plot and composition by species, with the tables just below.
- **Height:** height of juveniles per plot, with the panel of the collections of each year and the table below.
- **Age:** density against plot age (0 to 10 years), linear or logarithmic, with an optional fitted curve and equation.
- **Crossing:** height and density, as lines over the years or as a scatter plot with the line and equation.
- **Count by cohort:** individuals per year stacked by cohort, species or item, with a colour menu.
- **Jiménez schematic:** schematic of stand development next to the observed density.

**Check.** Collections and years identified, codes per year, records, species and height alerts.

**Export.** Clean tables (long and wide format) as CSV and Excel.
