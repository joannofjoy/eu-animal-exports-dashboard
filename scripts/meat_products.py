"""CN8 product codes for fresh/chilled and frozen bovine meat (CN headings
0201 and 0202) -- the "meat" side of the live-exports-vs-meat-imports
comparison on public/beef_vs_cows.html, as distinct from the live-animal
codes (heading 0102) that the rest of this project tracks.

Every code here was pulled live from Eurostat's own CN8 product codelist
(CXT_NC) rather than assumed -- 24 codes total, split by cut (carcass,
quarters, boneless) and weight band. **None of them distinguish veal from
beef by age.** This was confirmed directly against the codelist response:
not one of the 24 code names mentions veal, age, or the EU's own legal
Class V/Z veal categories (Regulation (EU) No 1308/2013) -- the same
weight-band-only limitation already found on the live-animal side (see
docs/llm_agent_handoff.md section 6). So a reporter's "beef & veal meat
imports" total below is genuinely a combined beef-and-veal figure, not an
approximation that could later be split -- there's no finer code to split
it on. docs/llm_agent_handoff.md section 6.1 has the full research trail,
including why industry and NGO sources don't have a cleaner number either.
"""

MEAT_PRODUCTS = [
    # 0201 -- meat of bovine animals, fresh or chilled
    "02011000",
    "02011010",
    "02011090",
    "02012011",
    "02012019",
    "02012020",
    "02012021",
    "02012029",
    "02012030",
    "02012031",
    "02012039",
    "02012050",
    "02012051",
    "02012059",
    "02012090",
    "02013000",
    # 0202 -- meat of bovine animals, frozen
    "02021000",
    "02022010",
    "02022030",
    "02022050",
    "02022090",
    "02023010",
    "02023050",
    "02023090",
]
