# Troubleshooting

**Header not found.** The sheet must have, within its first 25 rows, a row with tree identifier, species, DBH and condition. Compare with the data template.

**Many unknown species.** Check the region in the sidebar or add the aliases you use to the species table.

**Area warning.** The spreadsheet has no plot area. Write the label and value in the sheet header or give the area in the sidebar.

**Stem with DBH and no condition.** Choose whether it is excluded, counted as live or as dead.

**Ambiguous species (`Rh`, `Pe`).** Use the species code (`Rm`, `As`...) or register an alias in the species table.

**Repeated tags or a number of stems different from the declared one.** These are warnings: check the field spreadsheet.

**A year appears twice in the temporal analysis.** The values are averaged. Check that there are no repeated sheets.

**The CSV opens with glued columns.** Use the Excel file or the TXT.

**A change in the code does not show up (running from source).** Install in editable mode (`pip install -e .`) and restart the app.

The full list of checks is in [Data format](../data-format.md#validation).
