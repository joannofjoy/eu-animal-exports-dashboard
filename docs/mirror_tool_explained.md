# The mirror-statistics tool, explained

A beginner-level, function-by-function walkthrough of the code behind
`public/mirror.html` (the "Spiegelstatistik" / Austria-vs-partner-country
tool). This doc exists so the code is understandable on its own, not just
runnable -- if you already know pandas/requests/Chart.js well, skip
straight to the source files, the comments there cover the same ground
more tersely.

Four new files, three jobs:

```
scripts/fetch_mirror_data.py   -- talks to Eurostat's API, saves a CSV
scripts/build_mirror.py        -- turns that CSV into a webpage
public/mirror.template.html    -- the webpage itself (HTML/CSS/JS)
tests/test_*.py                -- checks the Python logic without the network
```

Same three-stage pipeline as the rest of this project (see `README.md`):
**fetch → build → static HTML file**. Nothing here talks to the internet
at page-view time; all the real data got baked in when `build_mirror.py`
last ran.

---

## 1. `scripts/fetch_mirror_data.py`

### Libraries used, and what they're for

- **`pandas`** (imported as `pd`) -- a library for working with tables of
  data (like Excel or a spreadsheet, but in code). Its core object is the
  `DataFrame`: rows and columns, with fast, whole-column operations
  (see "vectorization" below) instead of writing a loop for everything.
- **`requests`** -- makes HTTP requests (the same kind your browser makes
  when you visit a URL). `requests.get(url, params=...)` fetches a page
  or, here, a CSV file from Eurostat's API.
- **`io.BytesIO`** -- `requests` gives you the downloaded data as raw
  bytes (`response.content`), not a file on disk. `pandas.read_csv()`
  normally expects a filename or an open file. `BytesIO` wraps those raw
  bytes so they *look like* an open file to `read_csv()`, without
  actually saving anything to disk first.
- **`pathlib.Path`** -- represents a file/folder path (like
  `data/raw/foo.csv`) as an object with useful methods (`.exists()`,
  `.mkdir()`, `/` to join paths) instead of manipulating path strings by
  hand.

### What "vectorization" means here

A few messages before this doc was written, the question came up: does
this code use loops (like R's `lapply`/`sapply`), or vectorized
operations? Short answer: mostly vectorized, with one deliberate loop --
see the "vectorized vs. loop" note in `build_mirror.py`'s section below
for the full comparison. In this file specifically:

- `df["TIME_PERIOD"].str.slice(0, 4)` runs across the *entire column* at
  once (turning `"2024-03"` into `"2024"` for every row simultaneously),
  not one string at a time in a Python loop.
- `df.groupby([...])["OBS_VALUE"].sum()` is a vectorized group-and-add,
  pandas' equivalent of a spreadsheet pivot table.

### Function-by-function

**`eu_partner_countries(at_export_path)`**
Reads the *already existing* file of Austria's own export data
(`at_bovine_exports_yearly_by_partner_product.csv`, produced by the
separate `fetch_at_history.py` script) and returns the list of EU
countries Austria has ever sent cattle to. `set(...) & EU_MEMBERS` is a
**set intersection** -- "give me only the values present in both sets" --
Python's built-in way of answering "which of these partner codes are
also EU members?" in one line instead of a manual loop with an `if`
check.

**`fetch_series(reporters, partners, flow, indicator, raw_name)`**
Does the actual network request. Builds a query string like
`M.HR+DE+IT.AT.01022110+01022130+....1.SUPPLEMENTARY_QUANTITY` (a
dot-separated key, `+` meaning "or" within one field -- Eurostat's own
query syntax, not a Python thing), fetches it, saves the raw response to
`data/raw/` untouched (so there's always a record of exactly what
Eurostat returned), then parses it into a DataFrame.

The **f-string** (`f"M.{'+'.join(reporters)}...."`) is Python's built-in
way to build a string with variables spliced in -- the `{...}` parts get
replaced with their values. `'+'.join(reporters)` turns a list like
`["HR", "DE", "IT"]` into the single string `"HR+DE+IT"`.

**`to_yearly(df, value_col)`**
Eurostat returns one row per *month*. This collapses that down to one row
per *year* by grouping and summing, matching the granularity the rest of
the project uses. The `if df.empty:` check at the top exists because an
empty DataFrame (a query that matched nothing) can't be grouped the
normal way -- pandas needs to be told explicitly what the empty result's
column names should be, or later code that expects those columns to
exist would crash.

**`combine_series(at_export_units, partner_import_units, at_export_kg, partner_import_kg)`**
Takes four separate tables (Austria's export side and each partner
country's own import side, in two different units of measurement) and
joins them into one wide table using `.merge(..., how="outer")`. An
**outer join** (a concept from SQL/database theory, not unique to
pandas) keeps *every* row from *both* sides, even ones that only exist on
one side -- e.g. if Austria reported exporting to Croatia but Croatia
reported nothing at all, an outer join keeps that row instead of silently
dropping it. Rows that only exist on one side get `NaN` ("not a number",
pandas' marker for "no value here") on the other side's columns; this
function then replaces those with real zeros, since "no value" and
"legitimately zero" mean the same thing for this tool's purposes.

This function is deliberately **pure** (see below) so it can be tested
with small hand-built tables instead of needing a live internet
connection every time the tests run.

**`build_comparison_table(countries)`**
The orchestrator: calls `fetch_series()` three times (once per new data
series needed), reshapes Austria's *already-cached* export data to match,
and hands everything to `combine_series()`.

**`main()`**
Runs everything and saves the final result to
`data/processed/mirror_comparison.csv`. Guarded by
`if __name__ == "__main__":` -- a standard Python idiom meaning "only run
this when the file is executed directly (`python fetch_mirror_data.py`),
not when some other file imports functions from it."

### "Pure functions" -- why some functions take data in and return data out, with no side effects

You'll see this phrase in the code comments. A **pure function** is one
that (a) only depends on the values passed into it, and (b) doesn't
change anything outside itself (no network calls, no file writes, no
modifying a variable that lives outside the function). `combine_series()`
and `to_yearly()` are pure; `fetch_series()` is not (it makes a network
request and writes a file). Pure functions are much easier to test: you
can hand them fake, tiny input and check the output, without needing the
real Eurostat API to be up and returning the same numbers every time you
run the test suite.

---

## 2. `scripts/build_mirror.py`

### What it adds beyond fetch_mirror_data.py

Reshapes the flat CSV into the nested structure the webpage's JavaScript
needs, and writes the final `mirror.html` file by swapping placeholder
tokens (`__MIRROR_BY_COUNTRY_JSON__` etc.) in the template for real data.

### `load_mirror_by_country(processed_dir)` -- vectorized vs. loop, side by side

This is the function referenced in the earlier "vectorization" question.
It needs to produce a **nested dictionary** --
`{country: {year: {measure: {category: quantity}}}}` -- and there's no
single vectorized pandas operation that produces a nested Python
dict directly from a flat table. So this function uses **both**
approaches, each where it fits:

```python
for country, country_group in df.groupby("country"):      # <- plain loop
    for year, year_group in country_group.groupby("year"):  # <- plain loop
        for column, json_key in MEASURE_COLUMNS.items():    # <- plain loop
            by_category = (
                year_group.groupby("category")[column]      # <- vectorized
                .sum()
                .astype(int)
                .to_dict()
            )
```

The **outer loops** walk over groups (one country, one year, one measure
at a time) purely to build up the nested dictionary shape -- this part is
conceptually identical to R's `lapply(split(df, df$country), function(g) ...)`,
just written as Python's native `for` syntax instead of a function named
`apply`/`lapply`.

The **inner `.groupby("category")[column].sum()`** is the same kind of
vectorized, whole-column group-and-add used throughout
`fetch_mirror_data.py` -- pandas does this in fast, compiled code, not a
Python-level loop over individual rows.

`MEASURE_COLUMNS` is a plain dict at the top of the file mapping this
project's internal column names (`at_export_units`) to the
`camelCase` names the JavaScript side expects (`atExportUnits`) --
Python convention is `snake_case`, JavaScript convention is `camelCase`,
so this dict is the one place that translation happens, rather than
scattering `.replace()` calls everywhere.

### `render(template, mirror_by_country, countries, years)`

Identical pattern to every other `build_*.py` script in this project:
take the template's HTML as a plain string, replace `__TOKEN__`
placeholders with `json.dumps(...)` (Python's built-in function for
turning a dict/list into a JSON-formatted string) via repeated
`.replace()` calls, return the finished string. No templating library
(Jinja2 etc.) -- there are only a handful of fixed placeholders and no
loops/conditionals needed *within* the HTML itself, so a full template
engine would be more machinery than the job requires.

---

## 3. `public/mirror.template.html` -- the JavaScript

Everything below runs in the *browser*, not in Python -- once
`build_mirror.py` has swapped in real data and produced `mirror.html`,
the page is fully self-contained. Opening it doesn't talk to Eurostat, or
to any server at all.

### Chart.js

The bar chart is drawn by **Chart.js**, a JavaScript charting library
loaded from a CDN (`<script src="https://cdn.jsdelivr.net/...">`) --
this project doesn't install it locally, the browser fetches it once when
the page loads. `new Chart(canvasElement, { type: 'bar', data: {...},
options: {...} })` creates the chart; calling `.update()` on it later
redraws it with whatever's currently in `.data`.

### Key JS mechanisms, explained

- **`document.querySelectorAll('.catCheckbox')`** -- finds every element
  on the page matching a CSS selector (here, every checkbox with class
  `catCheckbox`) and returns them as a list-like object you can
  `.forEach()` over. The DOM (Document Object Model) is the browser's
  in-memory representation of the page's HTML; `document.querySelector*`
  is how JS reads/searches it.
- **`el.addEventListener('change', () => { ... })`** -- registers a
  function to run whenever that element fires a `change` event (a
  checkbox being ticked, a `<select>` dropdown's value changing, etc.).
  The `() => { ... }` is an **arrow function**, JavaScript's compact
  syntax for defining a small function inline, similar in spirit to a
  Python `lambda` but able to contain multiple statements.
- **`new Set(...)`** -- JavaScript's set type (same concept as Python's
  `set()` used in `fetch_mirror_data.py` above): an unordered collection
  with no duplicates, used here (`selectedCategories`) to track which
  category checkboxes are currently checked.
- **Template literals** -- backtick strings like
  `` `${countryName(selectedCountry)} (Import)` `` -- JavaScript's
  equivalent of Python f-strings; `${...}` splices a value into the
  string.
- **`Array.prototype.map()`** -- `years.map(y => valuesForYear(y).atExport)`
  transforms every element of an array into something else and returns a
  new array (here: turning a list of years into a list of "how many
  animals Austria exported that year"), the JS equivalent of a Python
  list comprehension.

### The data flow, end to end

1. `const mirrorByCountry = __MIRROR_BY_COUNTRY_JSON__;` -- this literal
   placeholder text got replaced with real JSON by `build_mirror.py`
   before the file was ever saved as `mirror.html`. By the time a browser
   opens it, this line just looks like a normal (very long) JavaScript
   object.
2. `sumCategories(byCategory)` reads `selectedCategories` (the Set from
   the checkboxes) and adds up only the categories currently checked --
   this is what lets the same underlying data answer "just the original
   two codes" or "everything" depending on the sidebar filter, without
   re-fetching anything.
3. `valuesForYear(year)` picks which of the four measures
   (`atExportUnits`/`atExportKg`/etc.) to read based on which tab
   (`selectedMeasure`) is active, then calls `sumCategories()` on it for
   both Austria's side and the partner's side.
4. `renderAll()` recomputes the chart's data arrays (one value per year,
   for each of the two bars) and calls `chart.update()` -- this is the
   one function that runs every time *any* filter, country, or tab
   changes, which is why every event listener above ends by calling it.

---

## 4. The tests

`tests/test_fetch_mirror_data.py` and `tests/test_build_mirror.py` use
**pytest**, this project's test runner (see
`~/.claude/skills/python-dev-conventions` for the project-wide
lint/test conventions). The `tmp_path` argument some tests take is a
built-in pytest **fixture** -- pytest automatically creates a fresh,
empty temporary folder for each test that asks for it (by naming
`tmp_path` as a parameter), so tests can write small fake CSV files
without touching the project's real data or leaving files behind
afterward.

Only the pure functions get tests (see the "pure functions" note above)
-- anything that makes a real network call is left untested here, the
same convention `fetch_at_history.py`'s tests already followed.
