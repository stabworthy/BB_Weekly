#!/usr/bin/env python3
"""
Blood Bowl Swiss Matchup Generator

Generates weekly matchups for a Blood Bowl league using a Swiss pairing system
that pairs highest-ranked teams while avoiding repeat matchups from past rounds.
"""

import csv
import sys
from typing import List, Set, Tuple, Optional
from pathlib import Path


def load_fixtures(fixtures_file: str) -> List[dict]:
    """
    Load fixtures from semicolon-delimited CSV file.
    
    Args:
        fixtures_file: Path to the fixtures CSV file
        
    Returns:
        List of dictionaries containing fixture data with tabs replaced
        
    Raises:
        FileNotFoundError: If the fixtures file doesn't exist
        ValueError: If the file format is invalid
    """
    fixtures_path = Path(fixtures_file)
    if not fixtures_path.exists():
        raise FileNotFoundError(f"Fixtures file not found: {fixtures_file}")
    
    fixtures = []
    try:
        with open(fixtures_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                # Replace tabs in all values
                cleaned_row = {k: v.replace('\t', ' ') if v else v for k, v in row.items()}
                fixtures.append(cleaned_row)
    except Exception as e:
        raise ValueError(f"Error reading fixtures file: {e}")
    
    return fixtures


def load_standings(standings_file: str) -> List[dict]:
    """
    Load standings from semicolon-delimited CSV file.
    
    Args:
        standings_file: Path to the standings CSV file
        
    Returns:
        List of dictionaries containing standings data with tabs replaced, sorted by Rank
        
    Raises:
        FileNotFoundError: If the standings file doesn't exist
        ValueError: If the file format is invalid
    """
    standings_path = Path(standings_file)
    if not standings_path.exists():
        raise FileNotFoundError(f"Standings file not found: {standings_file}")
    
    standings = []
    try:
        with open(standings_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                # Replace tabs in all values
                cleaned_row = {k: v.replace('\t', ' ') if v else v for k, v in row.items()}
                try:
                    rank = int(cleaned_row.get('Rank', 0))
                    if rank > 0:  # Only include valid ranks
                        standings.append(cleaned_row)
                except (ValueError, TypeError):
                    continue
        
        # Sort by Rank (ascending, Rank 1 = highest)
        standings.sort(key=lambda x: int(x.get('Rank', 0)))
    except Exception as e:
        raise ValueError(f"Error reading standings file: {e}")
    
    return standings


def extract_past_matchups(fixtures: List[dict]) -> Set[Tuple[str, str]]:
    """
    Extract and normalize past/scheduled matchups from fixtures.
    Any fixture in the file (played or scheduled) is treated as a used matchup
    so we never suggest the same pair again in a later round.
    
    Args:
        fixtures: List of fixture dictionaries
        
    Returns:
        Set of tuples (team1, team2) where team1 < team2 alphabetically
    """
    past_matchups = set()
    for fixture in fixtures:
        home_team = fixture.get('TeamNameHome', '').strip().replace('\t', ' ')
        away_team = fixture.get('TeamNameAway', '').strip().replace('\t', ' ')
        if not home_team or not away_team:
            continue
        matchup = tuple(sorted([home_team, away_team]))
        past_matchups.add(matchup)
    return past_matchups


def get_next_round_number(fixtures: List[dict]) -> int:
    """
    Determine the next round number from fixtures.
    
    Args:
        fixtures: List of fixture dictionaries
        
    Returns:
        Next round number (max round + 1), or 1 if no fixtures exist
    """
    rounds = []
    for fixture in fixtures:
        try:
            round_num = int(fixture.get('Round', 0))
            if round_num > 0:
                rounds.append(round_num)
        except (ValueError, TypeError):
            continue
    
    if not rounds:
        return 1
    
    return max(rounds) + 1


def have_played(team1: str, team2: str, past_matchups: Set[Tuple[str, str]]) -> bool:
    """
    Check if two teams have played each other before.
    
    Args:
        team1: First team name
        team2: Second team name
        past_matchups: Set of past matchup tuples
        
    Returns:
        True if teams have played before, False otherwise
    """
    clean_team1 = team1.strip().replace('\t', ' ')
    clean_team2 = team2.strip().replace('\t', ' ')
    matchup = tuple(sorted([clean_team1, clean_team2]))
    return matchup in past_matchups


def _find_pairing_without_repeats(
    teams: List[str],
    past_matchups: Set[Tuple[str, str]],
    unpaired_indices: List[int],
) -> Optional[List[Tuple[str, str]]]:
    """
    Backtracking search: find a set of pairings for unpaired_indices with no repeats.
    Pairs the highest-ranked (lowest index) unpaired team first, preferring
    higher-ranked opponents when multiple valid choices exist.
    
    Returns:
        List of (team1, team2) pairs, or None if no valid pairing exists.
    """
    if not unpaired_indices:
        return []
    # Always pair the highest-ranked (smallest index) unpaired team first
    i = unpaired_indices[0]
    team1 = teams[i]
    # Try opponents in order of rank (prefer pairing high with high)
    for j in unpaired_indices[1:]:
        team2 = teams[j]
        if have_played(team1, team2, past_matchups):
            continue
        rest_indices = [idx for idx in unpaired_indices if idx not in (i, j)]
        rest_pairings = _find_pairing_without_repeats(teams, past_matchups, rest_indices)
        if rest_pairings is not None:
            return [(team1, team2)] + rest_pairings
    return None


def generate_swiss_pairings(standings: List[dict], past_matchups: Set[Tuple[str, str]]) -> List[Tuple[Optional[str], Optional[str]]]:
    """
    Generate Swiss pairings for the next round with zero repeat matchups.
    
    Pairs highest-ranked teams together when possible, using backtracking to
    ensure no pair has played before. If odd number of teams, lowest ranked
    team gets a bye. If no valid pairing exists (e.g. some group has all
    played each other), raises ValueError.
    
    Args:
        standings: List of team standings sorted by Rank (ascending)
        past_matchups: Set of past matchup tuples
        
    Returns:
        List of tuples (team1, team2) for each matchup.
        Bye weeks are represented as (team_name, None)
        
    Raises:
        ValueError: If no valid pairing exists without repeats
    """
    teams = [team['TeamName'].strip().replace('\t', ' ') for team in standings]
    n = len(teams)
    
    # Odd number: assign bye to lowest ranked, then pair the rest
    if n % 2 == 1:
        bye_team = teams[-1]
        indices_to_pair = list(range(n - 1))
        pairings = _find_pairing_without_repeats(teams, past_matchups, indices_to_pair)
        if pairings is None:
            raise ValueError(
                "Cannot generate pairings with zero repeats: the remaining teams "
                "after assigning a bye have no valid matchups (all have already played each other). "
                f"Bye would be: {bye_team!r}. Consider manual adjustment or different bye assignment."
            )
        # Return matchups with bye first, then pairs (ordered by rank of first team)
        return [(bye_team, None)] + pairings
    
    # Even number: find a full pairing with no repeats
    pairings = _find_pairing_without_repeats(teams, past_matchups, list(range(n)))
    if pairings is None:
        raise ValueError(
            "Cannot generate pairings with zero repeats: no valid pairing exists. "
            "Some teams have all played each other (e.g. last 4 all played each other). "
            "Consider manual pairing or adding a bye for one team."
        )
    return pairings


def _build_matchup_rows(
    matchups: List[Tuple[Optional[str], Optional[str]]],
    next_round: int,
) -> List[List[str]]:
    """Build header and data rows for matchup output (cleans tabs from names)."""
    header = ['Round', 'Table', 'TeamNameHome', 'TeamNameAway']
    rows = [header]
    table_num = 1
    for team1, team2 in matchups:
        clean_team1 = team1.replace('\t', ' ') if team1 else ''
        clean_team2 = team2.replace('\t', ' ') if team2 else ''
        if team2 is None:
            rows.append([str(next_round), str(table_num), clean_team1, ''])
        else:
            rows.append([str(next_round), str(table_num), clean_team1, clean_team2])
        table_num += 1
    return rows


def write_matchups_csv(matchups: List[Tuple[Optional[str], Optional[str]]], 
                      next_round: int, 
                      output_file: str,
                      fixtures_template: List[dict]):
    """
    Write matchups to tab-delimited CSV file with simplified format.
    
    Args:
        matchups: List of matchup tuples
        next_round: Round number for these matchups
        output_file: Path to output CSV file
        fixtures_template: Original fixtures data (not used, kept for compatibility)
    """
    rows = _build_matchup_rows(matchups, next_round)
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        for row in rows:
            writer.writerow(row)


def write_matchups_csv_neat(matchups: List[Tuple[Optional[str], Optional[str]]],
                            next_round: int,
                            output_file: str,
                            fixtures_template: List[dict]):
    """
    Write matchups to a tab-delimited file with padded columns for human reading.
    Column widths are computed so that columns align when viewed in a text editor.
    
    Args:
        matchups: List of matchup tuples
        next_round: Round number for these matchups
        output_file: Path to output file
        fixtures_template: Original fixtures data (not used, kept for compatibility)
    """
    rows = _build_matchup_rows(matchups, next_round)
    if not rows:
        return
    num_cols = len(rows[0])
    widths = [0] * num_cols
    for row in rows:
        for c, cell in enumerate(row):
            widths[c] = max(widths[c], len(cell))
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        for row in rows:
            padded = [cell.ljust(widths[c]) for c, cell in enumerate(row)]
            f.write('\t'.join(padded) + '\n')


def validate_team_count(fixtures: List[dict], standings: List[dict], max_teams: int = 22):
    """
    Validate that we don't have more than max_teams unique team names.
    This catches cases where a team might have been renamed.
    
    Args:
        fixtures: List of fixture dictionaries
        standings: List of standings dictionaries
        max_teams: Maximum allowed number of unique teams
        
    Raises:
        ValueError: If more than max_teams unique team names are found
    """
    all_teams = set()
    
    # Collect teams from fixtures
    for fixture in fixtures:
        home = fixture.get('TeamNameHome', '').strip().replace('\t', ' ')
        away = fixture.get('TeamNameAway', '').strip().replace('\t', ' ')
        if home:
            all_teams.add(home)
        if away:
            all_teams.add(away)
    
    # Collect teams from standings
    for team in standings:
        team_name = team.get('TeamName', '').strip().replace('\t', ' ')
        if team_name:
            all_teams.add(team_name)
    
    if len(all_teams) > max_teams:
        sorted_teams = sorted(all_teams)
        raise ValueError(
            f"Error: Found {len(all_teams)} unique team names (expected maximum {max_teams}). "
            f"This may indicate a team was renamed. "
            f"Unique teams found: {', '.join(sorted_teams)}"
        )


def main():
    """Main program entry point."""
    # Default file names
    fixtures_file = 'waco-wizards-cup-season-2-fixtures.csv'
    standings_file = 'waco-wizards-cup-season-2-season-main-standings.csv'
    output_file = 'next_week_matchups.csv'
    output_file_neat = 'next_week_matchups_neat.txt'
    
    try:
        # Load data
        print("Loading fixtures...")
        fixtures = load_fixtures(fixtures_file)
        print(f"Loaded {len(fixtures)} fixtures")
        
        print("Loading standings...")
        standings = load_standings(standings_file)
        print(f"Loaded {len(standings)} teams")
        
        if not standings:
            print("Error: No teams found in standings file", file=sys.stderr)
            sys.exit(1)
        
        # Validate team count (check for renamed teams)
        print("Validating team count...")
        validate_team_count(fixtures, standings, max_teams=22)
        
        # Extract past matchups
        print("Extracting past matchups...")
        past_matchups = extract_past_matchups(fixtures)
        print(f"Found {len(past_matchups)} unique past matchups")
        
        # Determine next round
        next_round = get_next_round_number(fixtures)
        print(f"Next round: {next_round}")
        
        # Generate pairings
        print("Generating Swiss pairings...")
        matchups = generate_swiss_pairings(standings, past_matchups)
        
        # Display results
        print(f"\nGenerated {len(matchups)} matchups for Round {next_round}:")
        print("-" * 60)
        for i, (team1, team2) in enumerate(matchups, 1):
            if team2 is None:
                print(f"Table {i}: {team1} - BYE")
            else:
                print(f"Table {i}: {team1} vs {team2}")
        
        # Write to CSV (compact) and neat (padded for human reading)
        print(f"\nWriting matchups to {output_file}...")
        write_matchups_csv(matchups, next_round, output_file, fixtures)
        print(f"Successfully wrote matchups to {output_file}")
        print(f"Writing human-readable matchups to {output_file_neat}...")
        write_matchups_csv_neat(matchups, next_round, output_file_neat, fixtures)
        print(f"Successfully wrote matchups to {output_file_neat}")
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
