# Methods

This document gives every formula, convention and source used by MangueTREE v1.0.1, and the decisions that the sources do not settle. Notation: DBH in cm, $A$ is the plot area in m², $N$ is the number of stems. Page numbers refer to the works listed in the [References](#references).

## 1. Field conventions

**Counting unit: the stem.** When a trunk forks below breast height, or sprouts from a common base, each branch is measured as a separate stem (Cintrón & Schaeffer-Novelli 1984, p. 92). Densities are therefore stems per hectare. Cintrón & Schaeffer-Novelli use "number of individuals" in relative density; MangueTREE and the NEMA protocol use stems.

**Condition.** Each stem is classified as live or dead (Estrada 2013, p. 150, citing Cintrón & Schaeffer-Novelli 1984 and Schaeffer-Novelli & Cintrón 1986; the same convention is applied in the Guaratiba case study of Soares et al. 2017, p. 103). Stems with a blank condition are excluded by default; the user can instead count them as live or dead. Unrecognised condition codes are always excluded.

**Height is analysed for live stems only.** The NEMA protocol does not measure height on dead trees (Estrada 2013, p. 151). Mean, standard deviation, minimum, maximum and canopy height therefore use live stems. A dead stem that has a recorded height raises a validation warning and its height is ignored. Heights that are zero or negative are excluded from every height statistic. The source of this rule in the original guide (Schaeffer-Novelli & Cintrón 1986) was not available to us, so the citation above is to the protocols that apply it.

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

**Mortality.** The NEMA spreadsheet reports dead density and dead basal area, and Soares et al. (2017, tables 1 to 3) report the contribution of dead basal area in percent. The percentage forms below are the definition used by MangueTREE; no specific source gives these formulas:

$$M_{stems} = 100\,\frac{n_{dead}}{n_{live}+n_{dead}} \qquad M_{BA} = 100\,\frac{BA_{dead}}{BA_{live}+BA_{dead}}$$

**Stems per tree:** $n_{live\ stems}/n_{live\ trees}$, an indicator of multi-stemming. Cintrón & Schaeffer-Novelli (1984, p. 93) suggest recording the mean number of stems per clump in *Avicennia* and *Laguncularia*.

## 3. DBH classes

**Fixed classes.** The default cutoffs are 2.5 and 10 cm, which give three classes: $DBH < 2.5$, $2.5 \le DBH < 10$ and $DBH \ge 10$. The user can change the cutoffs. Classes are closed on the left, $[\text{lower}, \text{upper})$: a stem of exactly 2.5 cm falls in the middle class and a stem of exactly 10 cm in the upper class, as in the NEMA spreadsheet. Density and basal area are given per class and species, for live stems. Cintrón & Schaeffer-Novelli (1984, p. 92) mention class limits of 2.5, 5 and 10 cm.

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

The species table (sources: Tomlinson 2016; Spalding et al. 2010; Polidoro et al. 2010; Schaeffer-Novelli et al. 1990; Ximenes et al. 2016; Duke 2020) lists ten Neotropical mangrove and associated taxa, each with its own unique two-letter code (Rm, Rr, Rx, Ag, As, Ab, Lg, Ce, Pr, Pb; genus initial plus a letter of the epithet, with Lg and Rx kept from the laboratory convention and the hybrid mark), aliases, the regions where it occurs and a source. Brazilian range limits follow Ximenes et al. (2016): *Rhizophora mangle* reaches Santa Catarina, *Avicennia schaueriana* and *Laguncularia racemosa* reach Laguna (Santa Catarina), *A. germinans* and *Conocarpus erectus* reach Rio de Janeiro, and *R. racemosa* and *R. x harrisonii* occur only north of about 2.6 S (Maranhão). *Pelliciera* is split into *P. rhizophorae* (sensu stricto) and *P. benthamii* following Duke (2020). *R. x harrisonii* is treated as the hybrid of *R. mangle* and *R. racemosa* in most treatments, and its Caribbean and Pacific extent is to be confirmed. Four regions are defined: Brazil South and Southeast, Brazil North and Northeast, Caribbean and Western Atlantic, and Eastern Pacific (Americas). Genus abbreviations written in field sheets (for example "Av") are resolved with regional defaults only where the region has a single species of the genus: "Lg" is *L. racemosa* and "Cn", "Ce" and "Co" are *C. erectus* everywhere, "Av" is *A. schaueriana* in every region, following the NEMA/UERJ field sheets ("Ag" is used for *A. germinans*), and "Rh" is *R. mangle* in Brazil South and Southeast. "Rh" is ambiguous "Rh" in the other three regions and "Pe" in the Caribbean and the Eastern Pacific. Ambiguous entries are reported by the validation and treated as unidentified until the species code is used or an alias is added to the species table. This species and region table is provisional and awaits review by regional experts.

## References

1. Cintrón G, Schaeffer-Novelli Y (1984). Methods for studying mangrove structure. In: Snedaker SC, Snedaker JG (eds) The mangrove ecosystem: research methods. UNESCO, Paris, pp 91-113.
2. Pool DJ, Snedaker SC, Lugo AE (1977). Structure of mangrove forests in Florida, Puerto Rico, Mexico, and Costa Rica. Biotropica 9(3):195-212.
3. Soares MLG, Chaves FO, Estrada GCD, Fernandez V (2017). Mangrove forests associated with salt flats: a case study from southeast Brazil. Brazilian Journal of Oceanography 65(2):102-115. https://doi.org/10.1590/S1679-87592017083006502 (cited as a case study that applies the protocol in Guaratiba, not as a methods source)
4. Estrada GCD (2013). Análise espaço-temporal do sequestro e estoque de carbono na biomassa aérea de manguezais. PhD thesis, Universidade Federal do Rio de Janeiro, Programa de Pós-Graduação em Ecologia.
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
