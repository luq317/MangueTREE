# Contributing to MangueTREE

Thank you for your interest. Bug reports, data problems, species additions, translations and code are welcome.

## Development setup

```bash
git clone https://github.com/luq317/MangueTREE.git
cd MangueTREE
python -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e ".[test]"   # editable install; without -e the app keeps reading an old copy
```

Python 3.11 or newer is required. The PDF tests use `pdftotext` (package `poppler-utils` on Linux, `brew install poppler` on macOS).

## Running the tests

```bash
python -m pytest -q
```

The suite includes reference tests that compare the engine with the laboratory spreadsheet values in `tests/data/reference_values.csv`. A change that alters a published number must update those values deliberately and explain why in the pull request.

## Commits and pull requests

- Work on a branch and open a pull request against `main`.
- Write commit messages as `type: short description`, with a type such as `feat`, `fix`, `docs`, `test`, `refactor` or `chore`.
- Add or update tests with the change, and keep the full suite passing.
- Do not use the em dash character in documentation. Keep the text direct.
- Keep `docs/methods.md` in step with any change to a formula or convention.

## Adding species

1. Add a row to `src/manguetree/data/species_neotropics.csv` with `code`, `scientific_name`, `genus`, `aliases` (separated by `|`), `regions` (separated by `|`), `true_mangrove` and `source`.
2. If the genus has a regional default for abbreviations, update `src/manguetree/data/genus_defaults.csv`. Do not set a default where a genus has more than one species in the region.
3. Add a test to `tests/test_species.py`, and cite the source of the occurrence data in the pull request.

Users can also extend the table inside the app without changing the package.

## Adding or changing translations

The interface texts are in `src/manguetree/locales/en.json` and `pt.json`, as flat key-value catalogs. Add every new key to both files. English is the default and the fallback. To add a language, create `xx.json` with the same keys and register the language in `src/manguetree/i18n.py`; the tests in `tests/test_i18n.py` check that catalogs are complete.

## Reporting problems

Open an issue at https://github.com/luq317/MangueTREE/issues with:

- the MangueTREE version and how you run it (app, desktop build or library),
- what you expected and what happened,
- a small data file that reproduces the problem, with sensitive information removed.

For a data problem, include the data-check panel output.
