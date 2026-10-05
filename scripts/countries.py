"""ISO2 partner-country code -> English display name.

This only covers the country codes that actually show up in Austria's
DS-045409 export data (2015-2025) -- it is not a general-purpose country
list. Names are the standard English short names for each country (a
German-locale version of this file existed earlier in the project; the
dashboards now default to English, with translation into other languages
planned outside this project's scope).

A plain dict, at module level, is a Python variable that exists for the
lifetime of the program once this file is imported -- other scripts just
write `from countries import COUNTRY_NAMES` and look codes up with
`COUNTRY_NAMES.get(code, code)` (the `.get(code, code)` falls back to the
raw code itself if it's ever missing, instead of crashing).
"""

COUNTRY_NAMES = {
    "AT": "Austria",
    "AL": "Albania",
    "AM": "Armenia",
    "AZ": "Azerbaijan",
    "BA": "Bosnia and Herzegovina",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "CH": "Switzerland",
    "CI": "Côte d'Ivoire",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "DZ": "Algeria",
    "EE": "Estonia",
    "ER": "Eritrea",
    "ES": "Spain",
    "FR": "France",
    "GB": "United Kingdom",
    "GE": "Georgia",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IR": "Iran",
    "IT": "Italy",
    "KG": "Kyrgyzstan",
    "KZ": "Kazakhstan",
    "LB": "Lebanon",
    "LT": "Lithuania",
    "LV": "Latvia",
    "MA": "Morocco",
    "ME": "Montenegro",
    "MK": "North Macedonia",
    "MN": "Mongolia",
    "NL": "Netherlands",
    "PE": "Peru",
    "PT": "Portugal",
    "PL": "Poland",
    "QA": "Qatar",
    "RO": "Romania",
    "RU": "Russia",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "SN": "Senegal",
    "TM": "Turkmenistan",
    "TN": "Tunisia",
    "TR": "Türkiye",
    "UA": "Ukraine",
    "UZ": "Uzbekistan",
    "XK": "Kosovo",
    "XS": "Serbia",
    # Added once Germany/Ireland/Spain/France/Netherlands were fetched as
    # additional reporters -- this file originally only covered the codes
    # that showed up in Austria's own export data (see the module
    # docstring), so a much wider set of destination countries showed up
    # as bare, unnamed ISO2 codes in the UI the moment a different
    # reporter was picked. Cross-checked against Eurostat's own CXT_FREE_ISO
    # codelist, not guessed.
    "AD": "Andorra",
    "AE": "United Arab Emirates",
    "AF": "Afghanistan",
    "BF": "Burkina Faso",
    "BY": "Belarus",
    "CM": "Cameroon",
    "CO": "Colombia",
    "EG": "Egypt",
    "ET": "Ethiopia",
    "FI": "Finland",
    "GA": "Gabon",
    "GN": "Guinea",
    "IL": "Israel",
    "IN": "India",
    "IQ": "Iraq",
    "JO": "Jordan",
    "JP": "Japan",
    "KE": "Kenya",
    "KR": "South Korea",
    "KW": "Kuwait",
    "LU": "Luxembourg",
    "LY": "Libya",
    "MD": "Moldova",
    "ML": "Mali",
    "MR": "Mauritania",
    "MT": "Malta",
    "MX": "Mexico",
    "OM": "Oman",
    "PK": "Pakistan",
    "RW": "Rwanda",
    "SA": "Saudi Arabia",
    "SE": "Sweden",
    "SY": "Syria",
    "TH": "Thailand",
    "TJ": "Tajikistan",
    "US": "United States",
    "VE": "Venezuela",
    # XC/XL are real Spanish exclaves on the North African coast, not
    # typos -- Eurostat gives them their own trade codes separate from
    # mainland Spain.
    "XC": "Ceuta",
    "XL": "Melilla",
}

# The 27 current EU member states (ISO2), for splitting partner countries
# into "EU" vs. "non-EU" in the dashboards' filter. A frozenset (like a
# set, but can't be accidentally modified after creation) since this is a
# fixed reference list, not something any script should be adding to at
# runtime. Not every code here shows up in AT's export data -- that's fine,
# `code in EU_MEMBERS` just answers False for any partner not in the EU.
EU_MEMBERS = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
    }
)

# Reporter countries this project has a full fetched pipeline for (each via
# `fetch_at_history.py --reporter <code>` and `fetch_at_imports.py
# --reporter <code>`), in the order they should appear in a reporter
# picker. Austria is first and is the one always baked directly into every
# page by default; the rest load their data on demand when picked -- see
# build_dashboard.py's main() for how the per-reporter JSON files are
# written. Comext only accepts EU member states as reporters (see
# fetch_at_history.py's module docstring), so this can only ever grow by
# adding more of the 27, never a non-EU code.
REPORTERS = [
    ("AT", "Austria"),
    ("DE", "Germany"),
    ("IE", "Ireland"),
    ("ES", "Spain"),
    ("FR", "France"),
    ("NL", "Netherlands"),
]
