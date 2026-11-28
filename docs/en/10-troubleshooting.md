# Troubleshooting

**Header not found.** The sheet must have, within its first 25 rows, a row with tree identifier, species, DBH and condition. Compare with the data template.

**Missing columns.** The message says which columns are missing and which names are accepted (for example `DAP`, `dbh_cm`, `Status` for the condition). For CSV or TXT, the app tries `;`, `,` and tab when the chosen delimiter does not split the columns.

**No stem left for the calculation.** Every DBH is empty or invalid, or the condition codes are not recognised. The table below the message lists each problem. If the DBH is a formula, open the file in Excel and save it again.

**Unit converted warning.** The header said mm, cm or ha and the app converted it. Check that the conversion is the one you expect.

**Many unknown species.** Check the region in the sidebar or add the aliases you use to the species table.

**Area warning.** The spreadsheet has no plot area. Write the label and value in the sheet header or give the area in the sidebar.

**Stem with DBH and no condition.** Choose whether it is excluded, counted as live or as dead.

**Ambiguous species (`Rh`, `Pe`).** Use the species code (`Rm`, `As`...) or register an alias in the species table.

**Repeated tags or a number of stems different from the declared one.** These are warnings: check the field spreadsheet.

**A year appears twice in the temporal analysis.** The values are averaged. Check that there are no repeated sheets.

**The CSV opens with glued columns.** Use the Excel file or the TXT.

**A change in the code does not show up (running from source).** Install in editable mode (`pip install -e .`) and restart the app.

The full list of checks is in [Data format](../data-format.md#validation).
