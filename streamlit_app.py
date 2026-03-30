import csv
import io
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

from matchup_generator import (
    extract_past_matchups,
    generate_swiss_pairings,
    get_next_round_number,
    load_fixtures,
    load_standings,
    validate_team_count,
)


DEFAULT_FIXTURES = "waco-wizards-cup-season-2-fixtures.csv"
DEFAULT_STANDINGS = "waco-wizards-cup-season-2-season-main-standings.csv"


def _save_uploaded_file(uploaded_file) -> str:
    """Persist an uploaded file to a temp location and return its path."""
    suffix = Path(uploaded_file.name).suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


def _extract_csv_paths_from_zip(uploaded_zip) -> tuple[str, str]:
    """
    Extract fixtures/standings CSVs from an uploaded ZIP and return temp file paths.

    Matching is done by filename keywords:
    - fixtures file name contains "fixtures"
    - standings file name contains "standings"
    """
    zip_bytes = io.BytesIO(uploaded_zip.getvalue())
    with zipfile.ZipFile(zip_bytes) as zf:
        file_names = zf.namelist()
        fixtures_matches = [
            name
            for name in file_names
            if name.lower().endswith(".csv") and "fixtures" in Path(name).name.lower()
        ]
        standings_matches = [
            name
            for name in file_names
            if name.lower().endswith(".csv") and "standings" in Path(name).name.lower()
        ]

        if not fixtures_matches:
            raise ValueError("No CSV containing 'fixtures' found in the ZIP file.")
        if not standings_matches:
            raise ValueError("No CSV containing 'standings' found in the ZIP file.")
        if len(fixtures_matches) > 1:
            raise ValueError(
                "Multiple CSV files containing 'fixtures' found in the ZIP. "
                "Please include only one."
            )
        if len(standings_matches) > 1:
            raise ValueError(
                "Multiple CSV files containing 'standings' found in the ZIP. "
                "Please include only one."
            )

        fixtures_name = fixtures_matches[0]
        standings_name = standings_matches[0]

        with zf.open(fixtures_name) as src:
            fixtures_bytes = src.read()
        with zf.open(standings_name) as src:
            standings_bytes = src.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as fixtures_tmp:
        fixtures_tmp.write(fixtures_bytes)
        fixtures_path = fixtures_tmp.name
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as standings_tmp:
        standings_tmp.write(standings_bytes)
        standings_path = standings_tmp.name

    return fixtures_path, standings_path


def _build_output_files(matchups, next_round: int) -> tuple[str, str]:
    """Build compact TSV and padded TXT outputs in memory."""
    rows = [["Round", "Table", "TeamNameHome", "TeamNameAway"]]
    for table_num, (team1, team2) in enumerate(matchups, start=1):
        rows.append(
            [
                str(next_round),
                str(table_num),
                (team1 or "").replace("\t", " "),
                (team2 or "").replace("\t", " "),
            ]
        )

    # Compact tab-delimited output
    tsv_buffer = io.StringIO()
    writer = csv.writer(tsv_buffer, delimiter="\t")
    writer.writerows(rows)
    compact_output = tsv_buffer.getvalue()

    # Human-readable padded output
    widths = [max(len(row[c]) for row in rows) for c in range(len(rows[0]))]
    neat_lines = []
    for row in rows:
        padded = [cell.ljust(widths[c]) for c, cell in enumerate(row)]
        neat_lines.append("\t".join(padded))
    neat_output = "\n".join(neat_lines) + "\n"

    return compact_output, neat_output


def _render_matchups(matchups):
    for i, (team1, team2) in enumerate(matchups, start=1):
        if team2 is None:
            st.write(f"Table {i}: {team1} - BYE")
        else:
            st.write(f"Table {i}: {team1} vs {team2}")


def main():
    st.set_page_config(page_title="BB Weekly Matchup Generator", page_icon="🏈")
    st.title("Blood Bowl Weekly Matchup Generator")
    st.caption("Swiss-style pairings with no repeat matchups.")

    st.subheader("1) Choose input files")
    use_defaults = st.checkbox(
        "Use default files from this repo",
        value=True,
        help="Uncheck to upload a ZIP containing fixtures and standings CSV files.",
    )

    fixtures_path = None
    standings_path = None

    if use_defaults:
        if not Path(DEFAULT_FIXTURES).exists() or not Path(DEFAULT_STANDINGS).exists():
            st.error(
                "Default files were not found in this deployment. "
                "Uncheck 'Use default files' and upload a ZIP file manually."
            )
        else:
            fixtures_path = DEFAULT_FIXTURES
            standings_path = DEFAULT_STANDINGS
            st.success("Using default CSV files from the repository.")
    else:
        zip_upload = st.file_uploader("League ZIP file", type=["zip"])
        if zip_upload:
            try:
                fixtures_path, standings_path = _extract_csv_paths_from_zip(zip_upload)
                st.success(
                    "ZIP processed successfully. Found one fixtures CSV and one standings CSV."
                )
            except Exception as exc:
                st.error(f"Unable to process ZIP: {exc}")

    st.subheader("2) Generate pairings")
    if st.button("Generate Matchups", type="primary"):
        if not fixtures_path or not standings_path:
            st.warning(
                "Please use default files or upload a ZIP containing fixtures/standings CSVs."
            )
            return

        try:
            fixtures = load_fixtures(fixtures_path)
            standings = load_standings(standings_path)

            if not standings:
                st.error("No teams found in standings file.")
                return

            validate_team_count(fixtures, standings, max_teams=22)
            past_matchups = extract_past_matchups(fixtures)
            next_round = get_next_round_number(fixtures)
            matchups = generate_swiss_pairings(standings, past_matchups)

            st.success(f"Generated {len(matchups)} matchups for round {next_round}.")
            _render_matchups(matchups)

            compact_output, neat_output = _build_output_files(matchups, next_round)

            st.subheader("3) Download output")
            st.download_button(
                "Download compact output (TSV)",
                compact_output,
                file_name="next_week_matchups.csv",
                mime="text/tab-separated-values",
            )
            st.download_button(
                "Download human-readable output (TXT)",
                neat_output,
                file_name="next_week_matchups_neat.txt",
                mime="text/plain",
            )
        except Exception as exc:
            st.error(f"Failed to generate matchups: {exc}")


if __name__ == "__main__":
    main()
