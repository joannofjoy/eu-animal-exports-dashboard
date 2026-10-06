# Project documentation

This folder is internal project documentation. It is not copied into the
published site or the reader sharing bundle.

- [`llm_agent_handoff.md`](llm_agent_handoff.md) records the design history,
  standing constraints and non-obvious implementation decisions. It is a
  chronological handoff; verify current behavior in code and the README.
- [`eurostat_comext_api.md`](eurostat_comext_api.md) documents dataset and
  API choices used by the data pipeline.
- [`croatia_2024_anomaly.md`](croatia_2024_anomaly.md) records a specific
  data-quality investigation. It is an internal analysis, not a general
  warning about the published data.
- [`mirror_tool_explained.md`](mirror_tool_explained.md) explains the
  internal Austria-to-partner reconciliation tool.
- [`progress_notes.md`](progress_notes.md) is historical prototype context;
  it describes an earlier PHP version and is not current operating guidance.
- `references/` contains source material and supporting data for the
  investigations above.

The reader-facing explanation of scope, definitions and limitations lives
in [`../public/methodology.html`](../public/methodology.html). Keep the two
layers distinct: explain how to read the published figures on the site;
keep implementation history, exploratory findings and working notes here.
