# Methods

This document gives every formula, convention and source used by MangueTREE v1.3.1, and the decisions that the sources do not settle. Notation: DBH in cm, $A$ is the plot area in m², $N$ is the number of stems. Page numbers refer to the works listed in the [References](#references).

## 1. Field conventions

**Counting unit: the stem.** When a trunk forks below breast height, or sprouts from a common base, each branch is measured as a separate stem (Cintrón & Schaeffer-Novelli 1984, p. 92). Densities are therefore stems per hectare. Cintrón & Schaeffer-Novelli use "number of individuals" in relative density; MangueTREE and the NEMA protocol use stems.

**Condition.** Each stem is classified as live or dead (Estrada et al. 2013, citing Cintrón & Schaeffer-Novelli 1984 and Schaeffer-Novelli & Cintrón 1986; the same convention is applied in the Guaratiba case study of Soares et al. 2017, p. 103). Stems with a blank condition are excluded by default; the user can instead count them as live or dead. Unrecognised condition codes are always excluded.

**Height is analysed for live stems only.** The NEMA protocol does not measure height on dead trees (Estrada et al. 2013). Mean, standard deviation, minimum, maximum and canopy height therefore use live stems. A dead stem that has a recorded height raises a validation warning and its height is ignored. Heights that are zero or negative are excluded from every height statistic. The source of this rule in the original guide (Schaeffer-Novelli & Cintrón 1986) was not available to us, so the citation above is to the protocols that apply it.

**One height per tree.** Height is recorded for the individual (usually on its first row), not for each stem. Statistics use the recorded values.

## 2. Structural parameters

**Stem basal area** (Cintrón & Schaeffer-Novelli 1984, p. 92; applied in the Guaratiba case study of Soares et al. 2017, p. 103):

$$g = \frac{\pi}{4}\,\frac{DBH^2}{10\,000} = 0.00007854\,DBH^2 \quad (\text{m}^2)$$

**Expansion factor to one hectare:**

$$f = \frac{10\,000}{A}$$

**Basal area per hectare** (live, dead and total), the sum of the stem basal areas per unit area (Cintrón & Schaeffer-Novelli 1984, p. 92):

$$BA = f \sum g_i \quad (\text{m}^2\,\text{ha}^{-1})$$

**Density** (live, dead and total; Cintrón & Schaeffer-Novelli 1984, p. 92 to 93):

$$n = f\,N \quad (\text{stems ha}^{-1})$$

**Mean DBH**, the diameter of the stem of mean basal area, not the arithmetic mean of the DBHs (Cintrón & Schaeffer-Novelli 1984, p. 93 to 94; live stems only, as in the Guaratiba case study of Soares et al. 2017, p. 103):

$$\overline{DBH} = \sqrt{\frac{BA_{live}\times 12\,732.39}{n_{live}}} \quad (\text{cm})$$

**Mean height and standard deviation:** arithmetic mean and sample standard deviation of the recorded heights of live stems.

**Mortality.** The protocol of the Mangrove Study Group of UERJ (NEMA/UERJ) reports dead density and dead basal area, and Soares et al. (2017, tables 1 to 3) report the contribution of dead basal area in percent. The percentage forms below are the definition used by MangueTREE; no specific source gives these formulas:

$$M_{stems} = 100\,\frac{n_{dead}}{n_{live}+n_{dead}} \qquad M_{BA} = 100\,\frac{BA_{dead}}{BA_{live}+BA_{dead}}$$

**Stems per tree:** $n_{live\ stems}/n_{live\ trees}$, an indicator of multi-stemming. Cintrón & Schaeffer-Novelli (1984, p. 93) suggest recording the mean number of stems per clump in *Avicennia* and *Laguncularia*.

## 3. DBH classes

**Fixed classes.** The default cutoffs are 2.5 and 10 cm, which give three classes: $DBH < 2.5$, $2.5 \le DBH < 10$ and $DBH \ge 10$. The user can change the cutoffs. Classes are closed on the left, $[\text{lower}, \text{upper})$: a stem of exactly 2.5 cm falls in the middle class and a stem of exactly 10 cm in the upper class, as in the NEMA/UERJ protocol. Density and basal area are given per class and species, for live stems. Cintrón & Schaeffer-Novelli (1984, p. 92) mention class limits of 2.5, 5 and 10 cm.

**Regular classes and De Liocourt's quotient.** Live stems are also counted in regular classes of user-defined width (5 cm by default), and the quotient between consecutive classes is

$$q_i = \frac{N_i}{N_{i+1}}$$

after De Liocourt (1898). MangueTREE reports $q$ and its mean as descriptive values. It does not interpret them automatically (for example as an "inverted J" or as recruitment failure).

## 4. Phytosociology

Computed for live stems with DBH > 0 and an identified species.

$$DeR_j = 100\,\frac{N_j}{\sum N} \qquad DoR_j = 100\,\frac{BA_j}{\sum BA}$$

$$FA_j = 100\,\frac{u_j}{U} \qquad FR_j = 100\,\frac{FA_j}{\sum FA}$$

$$IVI_j = DeR_j + DoR_j + FR_j \;(\max 300)$$

$u_j$ is the number of sampling units that contain species $j$ and $U$ is the total number of sampling units that contain live stems. Relative density, relative dominance, relative frequency and the importance value follow Cintrón & Schaeffer-Novelli (1984, p. 96), who credit the importance value to Curtis (1959).

Frequency depends on the size of the sampling unit and cannot be computed with a single unit (Cintrón & Schaeffer-Novelli 1984, p. 96). For this reason a single plot shows only the relative density and relative dominance of each species, and the IVI appears when several plots are analysed together, with the plots as sampling units. For pooled plots, absolute density and basal area are expressed per hectare of the total sampled area.

## 5. Holdridge complexity index

$$CI = s \times d \times b \times h \times 10^{-3}$$

where $s$ is the number of species, $d$ the number of stems, $b$ the basal area (m²) and $h$ the height of the forest (m), with $d$ and $b$ expressed per 0.1 ha. The index is from Holdridge (1967) and was applied to mangroves by Pool et al. (1977, p. 195 and 209).

Pool et al. (1977, table 2, p. 204) compute two indices, one for stems with DBH > 2.5 cm and one for stems with DBH > 10 cm, because most mangrove stems are between 2.5 and 10 cm (p. 209). MangueTREE computes both:

- $d$ and $b$ count all live stems with DBH above the cutoff, whether or not their species was identified, so that $d$ agrees with the plot density.
- $s$ counts identified species only.
- $h$ is the canopy height of the plot (see the decisions below).

## 6. Decisions and adaptations

1. **Canopy height is an adaptation of Pool et al. (1977).** Pool et al. (p. 195) used the height of the tallest tree in each 5 × 10 m subplot. MangueTREE has no subplot information in the data, so it uses the mean of the 10 tallest live heights of the plot. The number of trees is configurable (`canopy_n` in `calc.analyze` and `calc.structural_summary`). We did not find this rule in any of the sources.
2. **Two Holdridge indices, with consistent cutoffs.** Each index uses the same set of stems for $d$ and $b$, as in Pool et al. (1977). The count of species $s$ comes from identified species only.
3. **Heights of live stems only**, as described in section 1.
4. **Stems without an identified species.** Stems whose species is unknown or ambiguous (for example a genus abbreviation with no regional default) are counted in density, basal area, DBH classes and the Holdridge $d$ and $b$. They appear as "Unidentified" in the DBH-class tables and in the composition charts. They are excluded from the phytosociology table, which lists identified species only (including its denominators), and from species richness.
5. **Relative density uses stems**, not individuals (section 1).
6. **De Liocourt's $q$ is descriptive**, with no automatic interpretation (section 3).
7. **Species richness $s$ is not rescaled to 0.1 ha.** It is the number of species in the sampled plot. For plots smaller than 0.1 ha this deviates from Holdridge (1967) and Pool et al. (1977), who express $s$ on the 0.1 ha basis like $d$ and $b$.

## 7. Species table

The species table (sources: Tomlinson 2016; Spalding et al. 2010; Polidoro et al. 2010; Schaeffer-Novelli et al. 1990; Ximenes et al. 2016; Duke 2020) lists ten Neotropical mangrove and associated taxa, each with its own unique two-letter code (Rm, Rr, Rx, Ag, As, Ab, Lg, Ce, Pr, Pb; genus initial plus a letter of the epithet, with Lg and Rx kept from the laboratory convention and the hybrid mark), aliases, the regions where it occurs and a source. Brazilian range limits follow Ximenes et al. (2016): *Rhizophora mangle* reaches Santa Catarina, *Avicennia schaueriana* and *Laguncularia racemosa* reach Laguna (Santa Catarina), *A. germinans* and *Conocarpus erectus* reach Rio de Janeiro, and *R. racemosa* and *R. x harrisonii* occur only north of about 2.6 S (Maranhão). *Pelliciera* is split into *P. rhizophorae* (sensu stricto) and *P. benthamii* following Duke (2020). *R. x harrisonii* is treated as the hybrid of *R. mangle* and *R. racemosa* in most treatments, and its Caribbean and Pacific extent is to be confirmed. Four regions are defined: Brazil South and Southeast, Brazil North and Northeast, Caribbean and Western Atlantic, and Eastern Pacific (Americas). Genus abbreviations written in field sheets (for example "Av") are resolved with regional defaults only where the region has a single species of the genus: "Lg" is *L. racemosa* and "Cn", "Ce" and "Co" are *C. erectus* everywhere, "Av" is *A. schaueriana* in every region, following the NEMA/UERJ field sheets ("Ag" is used for *A. germinans*), and "Rh" is *R. mangle* in Brazil South and Southeast. "Rh" is ambiguous in the other three regions and "Pe" in the Caribbean and the Eastern Pacific. Ambiguous entries are reported by the validation and treated as unidentified until the species code is used or an alias is added to the species table. This species and region table is provisional and awaits review by regional experts.

## 8. Values added in version 1.1.0

- **Contribution of each species.** For density and basal area, live, dead and total: $100 \times$ (value of the species) / (value of all stems of that condition in the plot). The contributions of one condition add up to 100%. Relative density and relative dominance (section 4) are the live contributions of the identified species.
- **Mortality in basal area.** $100 \times BA_{dead} / BA_{total}$, next to the mortality in stems ($100 \times N_{dead} / N_{total}$).
- **Stems without DBH.** A stem needs a DBH > 0 to enter density and basal area, as in the protocol of the Mangrove Study Group of UERJ (NEMA/UERJ) (density counts the stems whose basal area is above zero). Stems without DBH are reported by the data check and counted per year in the temporal analysis (`n_dead_no_dbh`, `n_live_no_dbh`), so the user knows when the dead density and dead basal area are underestimated.
- **Count or per hectare.** Densities can be shown as stems per hectare or as the number of stems in the plot ($N = D \times A / 10\,000$).
- **Values by DBH class.** In the temporal analysis, live and dead density and basal area of each DBH class defined by the cutoffs.
- **Several plots in the temporal analysis.** Each workbook is one plot. The series can be shown per plot or as the mean ± standard deviation of the plots in each year. Sheets of the same plot and year are averaged, and a species absent from one of them counts as zero there. The difference chart shows $x_B - x_A$ per species and year.
- **Normalised profile (multiple plots).** Each parameter is divided by its largest value among the plots, so the plot with the largest value is at 1.

## 9. Reference curve of density against mean DBH (Jiménez et al. 1985)

Jiménez, Lugo and Cintrón (1985, Fig. 1) describe normal tree mortality as a negative power function of the mean DBH of the stand. Fitted to 114 stands of the Americas ($r^2 = 0.73$):

$$\ln y = \ln 7496 - 1.4934 \, \ln x$$

with $y$ in trees per 0.1 ha and $x$ the mean DBH in cm (the diameter of the tree of mean basal area, section 2). MangueTREE converts $y$ to stems per hectare ($\times 10$, that is $y = 74\,960 \, x^{-1.4934}$) and draws the curve under the plots (single plot, multiple plots and temporal pages), with density of live stems on the vertical axis. The curve is a reference for the comparison and not a test, and it is not applied to the juveniles of the colonization page, which have height and no DBH. There, the page repeats the reference values of Jiménez et al. (1985) in a note (more than 500,000 propagules per hectare falling to about 2,000 stems per hectare with 2.5 cm of mean DBH in less than five years; 40-70 seedlings per m² in *Rhizophora* and 140-330 per m² in *Avicennia*). Their Fig. 2, the stages of stem density over time (colonization, early development, maturity, senescence), is schematic and has no equation, so the app does not draw it.

## 10. Colonization dynamics page

The page reads the data-entry sheet of each NEMA/UERJ colonization workbook (one per plot) and ignores the calculation sheets. The check screen shows what was read before any result.

- **Codes and classes.** Codes are normalised (upper case, no spaces or asterisks). J is a juvenile (counts in density), PL a seedling, PR a propagule, TR an extra trunk, X, Y, N3 and M dead, N1 and N2 uncertain (outside density) and E excluded (outside every calculation). The user can reclassify any code of a workbook on the check screen, for example an unknown code; the new class changes density, height and the export, and lasts for the session.
- **Density and height.** Density counts the lines with code J per hectare (a repeated tag on two lines counts twice, as in the NEMA workbooks). By default every juvenile counts ("All, with and without a cohort"); the other option keeps only the juveniles whose cohort is not after the year; heights are typed in cm (shown in m or cm, as chosen in the sidebar), with the sample standard deviation.
- **Height of a year with more than one collection.** The height of a year does not always come from the last collection, which may lack part of the data. For every year the app reads all the height columns (one per collection) and the Height tab lists the mean, SD and N of each collection of the years that have more than one, with the one in use marked. By default the collection with the most measured heights is used (ties go to the latest); the user can instead use the last collection, or choose one collection per plot and year. The choice applies to the Height table, the height chart, the crossing chart and the exports. Density is not affected: it follows the codes of the last collection of the year.
- **Crossing height and density.** The Crossing tab (Charts) joins, per plot and year, the density of juveniles and their mean height. It draws them as lines over the years (density on the left axis, height with its SD on the right axis) or as X vs Y (a point per plot and year, the year written on the point, either variable on X), and gives the Pearson correlation per plot (at least three years). A year of a joined plot with only part of its plots is marked with the same asterisk.
- **Clean export.** One row per individual and collection (long) or one row per individual with a code and a height column per year (wide), with the collection, its date and year, the class, the cohort and a column that marks the collection that counts in each year.
- **Plot age and log-linear fit.** The year each plot was established comes from Estevam (2019, Fig. 2.2) and can be edited; age is the collection year minus that year, using only ages above zero. It counts the time since the plot was set up, not since colonization began, because the first plots already had individuals of an earlier cohort when they were demarcated. The page fits $\ln(\text{density}) = a + b \, \ln(\text{age})$ by least squares, jointly or per plot, and reports $b$, its standard error, $r^2$ and $n$. The points are repeated measures of the same plots, so these values are descriptive.
- **Joined plots.** A joined plot (for example H+I) is treated as one larger plot: the juveniles of its plots are added and divided by the sum of their areas, $d_{H+I} = (n_H + n_I)/(A_H + A_I)$. This is not the mean of the two densities, $(d_H + d_I)/2$; the two agree only when the areas are equal (60 m² each for H and I, 25 m² each for A and B), and the sum over the area stays correct if the areas differ or change over the years. Height pools the individuals of the plots (mean and standard deviation of the whole set), and relative density uses the density of the union. A union is **incomplete** in a year in which one of its plots was not sampled (H+I in 2016-2018, when only H was collected): the value is then that of the plots with data (here, H alone, in 6 m²), not of the whole union. The page marks those years with an asterisk and an open diamond in every chart, with a warning below tables and charts, and in the columns `membros`, `n_parcelas` and `incompleta` of the tables and CSV files. A check box hides the incomplete years from tables, charts and the PDF report.
- **Check screen, counts and joins.** The check also lists the codes per year, the records per collection, the species, the area used for each plot and height alerts (rows with J but no height, or above a limit). The list "To fix in the spreadsheet" points, with row, column and tag, at juveniles in a year before their cohort, unreadable cohorts, J heights that are zero, negative or above 600 cm and juveniles without species; none of them leaves the calculation, so the numbers change only when the spreadsheet is fixed. The Count by cohort chart counts individuals per year for any classes or codes, joined or kept apart, stacked by cohort, species or item. Plots can be joined freely (up to three groups) and the joins apply to every tab (see the next item); the height tab accepts any class. Settings are applied with the Run analysis button of the sidebar, and the texts of every chart can be edited in its Adjust menu.
- **Schematic of Jiménez et al. (1985).** Their Fig. 2 (colonization, early development, maturity and senescence of stem density) is redrawn as a qualitative schematic next to the observed density curve. The paper gives no equation or values for it, so the drawing has no scale.

## 11. Units, decimals and saved tables

- **Height unit.** The sidebar of every analysis page (single plot, multiple plots, temporal and colonization) has a metres/centimetres choice. Calculation stays in metres (structure) or in centimetres (colonization, as typed); the choice only changes what is shown and saved: tables, charts, Excel, CSV and TXT files, the summary panel and the PDF report. Axis titles, labels and column names carry the unit.
- **Two decimals.** Results in tables, labels and saved files have two decimals (0.00 in English, 0,00 in Portuguese), except counts, which are whole numbers. Chart axes keep the complete numbers (10.000, not 10K); the Excel file keeps the full value and shows it with two decimals, while CSV and TXT files are rounded to two. Densities, areas and percentages in the PDF texts, KPIs and the summary panel follow the same rule.
- **Table of every chart.** Each chart has a Chart table menu next to the save-as-picture button, with the data behind the chart (the values drawn, one column per series) as Excel, CSV or TXT. The page exports also offer the three formats.
- **File formats.** Excel is organised (one sheet per table, header, widths, number format). CSV is for Excel in Portuguese (semicolon separator, decimal comma, UTF-8 with BOM) or in English (comma and point). TXT is tab-separated.

## References

1. Cintrón G, Schaeffer-Novelli Y (1984). Methods for studying mangrove structure. In: Snedaker SC, Snedaker JG (eds) The mangrove ecosystem: research methods. UNESCO, Paris, pp 91-113.
2. Pool DJ, Snedaker SC, Lugo AE (1977). Structure of mangrove forests in Florida, Puerto Rico, Mexico, and Costa Rica. Biotropica 9(3):195-212.
3. Soares MLG, Chaves FO, Estrada GCD, Fernandez V (2017). Mangrove forests associated with salt flats: a case study from southeast Brazil. Brazilian Journal of Oceanography 65(2):102-115. https://doi.org/10.1590/S1679-87592017083006502 (cited as a case study that applies the protocol in Guaratiba, not as a methods source)
4. Estrada GCD, Soares MLG, Chaves FO, Cavalcanti VF (2013). Analysis of the structural variability of mangrove forests through the physiographic types approach. Aquatic Botany 111:135-143. https://doi.org/10.1016/j.aquabot.2013.06.003
5. Schaeffer-Novelli Y, Cintrón G (1986). Guia para estudo de áreas de manguezal: estrutura, função e flora. Caribbean Ecological Research, São Paulo, 150 p.
6. Holdridge LR (1967). Life zone ecology. Tropical Science Center, San José (cited through Pool et al. 1977, not consulted directly).
7. Curtis JT (1959). The vegetation of Wisconsin: an ordination of plant communities. University of Wisconsin Press, Madison (cited through Cintrón & Schaeffer-Novelli 1984, not consulted directly).
8. De Liocourt F (1898). De l'aménagement des sapinières. Bulletin trimestriel de la Société forestière de Franche-Comté et Belfort, juillet 1898: 396-409.
9. Tomlinson PB (2016). The botany of mangroves, 2nd ed. Cambridge University Press, Cambridge.
10. Spalding M, Kainuma M, Collins L (2010). World atlas of mangroves. Earthscan, London, 319 p.
11. Polidoro BA et al. (2010). The loss of species: mangrove extinction risk and geographic areas of global concern. PLoS ONE 5(4): e10095.
12. Schaeffer-Novelli Y, Cintrón-Molero G, Adaime RR, Camargo TM (1990). Variability of mangrove ecosystems along the Brazilian coast. Estuaries 13(2): 204-218.
13. Ximenes AC, Maeda EE, Arcoverde GFB, Dahdouh-Guebas F (2016). Spatial assessment of the bioclimatic and environmental factors driving mangrove tree species' distribution along the Brazilian coastline. Remote Sensing 8(6):451. https://doi.org/10.3390/rs8060451
14. Duke NC (2020). A systematic revision of the vulnerable mangrove genus Pelliciera (Tetrameristaceae) in equatorial America. Blumea 65:107-120. https://doi.org/10.3767/blumea.2020.65.02.04
15. Jiménez JA, Lugo AE, Cintrón G (1985). Tree mortality in mangrove forests. Biotropica 17(3):177-185. https://doi.org/10.2307/2388214
16. Cavalcanti VF, Soares MLG, Estrada GCD, Chaves FO (2009). Evaluating mangrove conservation through the analysis of forest structure data. Journal of Coastal Research SI 56:390-394.
17. Estevam MRM (2019). Os manguezais de Guaratiba frente às mudanças climáticas globais: análise da influência da variabilidade climática sobre a dinâmica de comunidades pioneiras. Tese (Doutorado), Programa de Pós-Graduação em Meio Ambiente, Universidade do Estado do Rio de Janeiro, Rio de Janeiro.
