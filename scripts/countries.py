"""ISO2 partner-country code -> English display name.

This covers the country codes currently present in the 27 EU reporters'
DS-045409 import/export data -- it is not a general-purpose country list.
Names are the standard English short names (translation into other
languages is outside this project's scope).

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
    "AU": "Australia",
    "AZ": "Azerbaijan",
    "BA": "Bosnia and Herzegovina",
    "BE": "Belgium",
    "BJ": "Benin",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "CA": "Canada",
    "CH": "Switzerland",
    "CI": "Côte d'Ivoire",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "CN": "China",
    "DE": "Germany",
    "DK": "Denmark",
    "DZ": "Algeria",
    "EE": "Estonia",
    "ER": "Eritrea",
    "ES": "Spain",
    "FR": "France",
    "GB": "United Kingdom",
    "GE": "Georgia",
    "GI": "Gibraltar",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "ID": "Indonesia",
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
    "NO": "Norway",
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
    # These additional destinations occur in the other reporters' data;
    # names were checked against Eurostat's CXT_FREE_ISO codelist.
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
    # Turned up only once all 27 reporters had data (small reporters trade
    # with a wider, more varied set of non-EU partners than Austria alone
    # did) -- names checked against Eurostat's CXT_FREE_ISO codelist, same
    # as the block above.
    "AR": "Argentina",
    "BR": "Brazil",
    "BS": "Bahamas",
    "CG": "Congo",
    "FO": "Faroe Islands",
    "IS": "Iceland",
    "MG": "Madagascar",
    "MY": "Malaysia",
    "NG": "Nigeria",
    "PS": "Occupied Palestinian Territory",
    "UG": "Uganda",
    "VN": "Vietnam",
    # Turned up once meat-trade data (fetch_meat_imports.py, headings
    # 0201/0202) was fetched for all 27 reporters -- meat ships to a much
    # wider set of destinations than live cattle does. Same verification
    # as the blocks above: checked live against CXT_FREE_ISO, not guessed.
    "AG": "Antigua and Barbuda",
    "BM": "Bermuda",
    "BO": "Bolivia",
    "BT": "Bhutan",
    "BW": "Botswana",
    "CL": "Chile",
    "DO": "Dominican Republic",
    "FK": "Falkland Islands",
    "GH": "Ghana",
    "GL": "Greenland",
    "GT": "Guatemala",
    "HK": "Hong Kong",
    "HN": "Honduras",
    "LI": "Liechtenstein",
    "NC": "New Caledonia",
    "NZ": "New Zealand",
    "PA": "Panama",
    "PM": "St Pierre and Miquelon",
    "PY": "Paraguay",
    "SG": "Singapore",
    "SZ": "Eswatini",
    "TW": "Taiwan",
    "TZ": "Tanzania",
    "UY": "Uruguay",
    "VG": "British Virgin Islands",
    "ZA": "South Africa",
    "ZM": "Zambia",
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
# fetch_at_history.py's module docstring) -- this is now all 27, so it
# can't grow further; alphabetical by code after Austria, matching
# EU_MEMBERS above. Verified GR (not EL, the code some other Eurostat
# datasets use for Greece) is the correct Comext reporter code for Greece
# via a live API call -- confirmed rather than assumed, since the two
# conventions genuinely differ across different Eurostat datasets.
REPORTERS = [
    ("AT", "Austria"),
    ("BE", "Belgium"),
    ("BG", "Bulgaria"),
    ("HR", "Croatia"),
    ("CY", "Cyprus"),
    ("CZ", "Czechia"),
    ("DK", "Denmark"),
    ("EE", "Estonia"),
    ("FI", "Finland"),
    ("FR", "France"),
    ("DE", "Germany"),
    ("GR", "Greece"),
    ("HU", "Hungary"),
    ("IE", "Ireland"),
    ("IT", "Italy"),
    ("LV", "Latvia"),
    ("LT", "Lithuania"),
    ("LU", "Luxembourg"),
    ("MT", "Malta"),
    ("NL", "Netherlands"),
    ("PL", "Poland"),
    ("PT", "Portugal"),
    ("RO", "Romania"),
    ("SK", "Slovakia"),
    ("SI", "Slovenia"),
    ("ES", "Spain"),
    ("SE", "Sweden"),
]
