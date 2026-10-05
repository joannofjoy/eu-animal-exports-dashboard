"""Runs the whole data pipeline end to end: re-fetch every reporter's
export and import data from the live Eurostat API, then rebuild every
page from the refreshed data. This is the one command a scheduled task
(or a person) needs to bring the whole site up to date -- before this
script existed, refreshing meant remembering to run fetch_at_history.py
and fetch_at_imports.py once per reporter (12 separate commands for the
six reporters this project tracks) and then all six build_*.py scripts,
in the right order, by hand.

Each step is a real subprocess call to the existing script, exactly as if
typed by hand -- this file doesn't duplicate any fetching/building logic,
it just sequences the scripts that already do that work. A failure in one
reporter's fetch (a network hiccup, Eurostat being briefly unavailable)
is logged and skipped rather than aborting the whole run, since the build
scripts already know how to skip a reporter with no data for it; a
failure in a build step is also logged and skipped, so one broken page
doesn't block the others from refreshing. The very end prints a summary
and exits non-zero if anything failed, so a scheduler can alert on it.

Run it directly:

    python scripts/refresh_all.py

Or wire it into Windows Task Scheduler (Action: "Start a program",
Program: path to this project's .venv/Scripts/python.exe, Arguments:
the full path to this file, Start in: the project root) for a hands-off
periodic refresh -- see docs/llm_agent_handoff.md for why this project
has no server-side cron equivalent (it's a static site, nothing is
"running" between refreshes).
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

from countries import REPORTERS

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
WORLD_BOUNDARIES_PATH = ROOT_DIR / "data" / "raw" / "ne_110m_admin_0_countries.geojson"

# Eurostat data starts in 2015 for this project (see fetch_at_history.py);
# the end year is always "whatever year it is right now," not a number
# that would need bumping by hand every January. Requesting months that
# haven't been published yet isn't an error -- Eurostat's API just omits
# them from the response, the same way a partial current year already
# shows up as a shorter bar on the yearly chart today.
START_YEAR = 2015
END_YEAR = date.today().year

# (script filename, extra CLI args) for the per-reporter fetch steps --
# both need a reporter and the same year range, so they're driven by one
# loop below rather than writing the same subprocess call out twice.
PER_REPORTER_FETCH_SCRIPTS = ["fetch_at_history.py", "fetch_at_imports.py"]

# Build scripts take no arguments and must run after every fetch step
# above, in no particular order relative to each other (each reads its
# own processed CSVs fresh) -- but all of them need the fetch steps done
# first, which is why this list is a separate, later phase below rather
# than interleaved with fetching.
BUILD_SCRIPTS = [
    "build_dashboard.py",
    "build_map.py",
    "build_monthly.py",
    "build_trade_pairs.py",
    "build_site.py",
    "build_mirror.py",
]


def run_step(description: str, args: list[str]) -> bool:
    """Runs one script as a subprocess (python.exe, same interpreter this
    script is running under, so it's the project's own .venv -- not
    whatever "python" happens to resolve to on PATH). Prints its output
    as it goes rather than capturing it, so a long-running fetch doesn't
    look stuck; returns whether it succeeded, so the caller can keep a
    running tally instead of stopping at the first failure.
    """
    # flush=True: without it, this print can sit in Python's own output
    # buffer and land in the log *after* the subprocess's own (separately
    # buffered) output below, even though it happened first -- confirmed
    # live, the progress headers came out jumbled relative to the actual
    # fetch/build messages the first time this ran with output redirected
    # to a file (a real terminal doesn't show the problem, which is what
    # made it easy to miss).
    print(f"\n=== {description} ===", flush=True)
    result = subprocess.run([sys.executable, *args], cwd=SCRIPTS_DIR)
    if result.returncode != 0:
        print(f"!!! FAILED: {description} (exit code {result.returncode})", flush=True)
        return False
    return True


def main() -> None:
    failures: list[str] = []

    if not WORLD_BOUNDARIES_PATH.exists():
        # Country boundary shapes don't change in any way that matters
        # for this project -- fetched once and cached, not re-fetched on
        # every refresh (that would just be wasted network calls against
        # Natural Earth's server for data that's already correct).
        ok = run_step("World boundaries (first run only)", ["fetch_world_boundaries.py"])
        if not ok:
            failures.append("fetch_world_boundaries.py")

    for code, name in REPORTERS:
        for script in PER_REPORTER_FETCH_SCRIPTS:
            description = f"{script} --reporter {code} ({name})"
            ok = run_step(
                description,
                [
                    script,
                    "--reporter",
                    code,
                    "--start-year",
                    str(START_YEAR),
                    "--end-year",
                    str(END_YEAR),
                ],
            )
            if not ok:
                failures.append(description)

    # Mirror Statistics is Austria-only and has no --reporter flag -- see
    # docs/llm_agent_handoff.md for why it never got the multi-reporter
    # rollout the other five pages did.
    ok = run_step("fetch_mirror_data.py (AT only)", ["fetch_mirror_data.py"])
    if not ok:
        failures.append("fetch_mirror_data.py")

    for script in BUILD_SCRIPTS:
        ok = run_step(script, [script])
        if not ok:
            failures.append(script)

    print("\n" + "=" * 60)
    if failures:
        print(f"Refresh finished with {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("Refresh finished -- every step succeeded.")


if __name__ == "__main__":
    main()
