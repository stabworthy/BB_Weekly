import csv
import io
import tempfile
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
        help="Uncheck to upload fresh fixtures/standings CSV files.",
    )

    fixtures_path = None
    standings_path = None

    if use_defaults:
        if not Path(DEFAULT_FIXTURES).exists() or not Path(DEFAULT_STANDINGS).exists():
            st.error(
                "Default files were not found in this deployment. "
                "Uncheck 'Use default files' and upload both files manually."
            )
        else:
            fixtures_path = DEFAULT_FIXTURES
            standings_path = DEFAULT_STANDINGS
            st.success("Using default CSV files from the repository.")
    else:
        fixtures_upload = st.file_uploader("Fixtures CSV", type=["csv"])
        standings_upload = st.file_uploader("Standings CSV", type=["csv"])
        if fixtures_upload and standings_upload:
            fixtures_path = _save_uploaded_file(fixtures_upload)
            standings_path = _save_uploaded_file(standings_upload)

    st.subheader("2) Generate pairings")
    if st.button("Generate Matchups", type="primary"):
        if not fixtures_path or not standings_path:
            st.warning("Please provide both fixtures and standings files.")
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
