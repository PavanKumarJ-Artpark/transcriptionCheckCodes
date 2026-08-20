"""
contentChecks.py — the transcription content checks, as a plain function over a
DataFrame.

Extracted from a transcription submission pipeline with the database, email and
bucket coupling removed, so the checks can be run against any project's data.
The set of checks and the order they run in are unchanged from the original.

Each enabled check adds one boolean `<check>_error` column to the DataFrame and
one ERROR Finding per failing row, plus a single batch-level finding when the
share of failing rows exceeds batch_minimum_rejected_threshold.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

import transcriptionCheckListFunction as tcl


@dataclass
class Finding:
    severity: str            # ERROR | WARNING | OK | INFO
    check: str
    row: Optional[int] = None
    key: Optional[str] = None
    column: Optional[str] = None
    message: str = ""


def is_enabled(cfg, name: str, default: bool = True) -> bool:
    """True if [CHECKS] <name> = true, or if it is not listed at all."""
    if cfg.has_section("CHECKS") and cfg.has_option("CHECKS", name):
        return cfg.getboolean("CHECKS", name)
    return default


def build_check_map(text: pd.Series, lang: Optional[pd.Series],
                    index, check_words_limit: int, invalid_ratio: float) -> Dict:
    """check name -> callable returning a boolean Series over the rows.

    Kept as lambdas so a disabled check is never evaluated — several of them
    are per-row Python and cost real time on a large delivery.
    """
    builders = {
        # Runs first: a blank value passes every other check below (they all
        # look FOR something wrong), so nothing else would catch it.
        "transcript_is_empty":
            lambda: text.apply(tcl.check_empty),
        "number_of_words_lt_threshold":
            lambda: text.apply(lambda t: tcl.check_words(t, check_words_limit)),
        "transcript_has_numbers":
            lambda: text.apply(tcl.check_numbers),
        "brackets_dont_have_open_close":
            lambda: text.apply(lambda t: tcl.check_brackets(t, brackets=["[]", "<>", "{}"])),
        "bracket_structure_invalid":
            lambda: text.apply(tcl.check_bracket_structure),
        "consecutive_duplicate_tag":
            lambda: text.apply(tcl.check_consecutive_duplicate_tag),
        "tag_spacing_missing":
            lambda: text.apply(tcl.check_tag_spacing),
        "script_inconsistency":
            lambda: text.apply(tcl.check_script_consistency),
        "inaudible":
            lambda: text.apply(lambda t: tcl.find_word(t, "audible", surround="[]")),
        "unintelligible":
            lambda: text.apply(lambda t: tcl.find_word(t, "unintelligible", surround="[]")),
        "PAUSE":
            lambda: text.apply(lambda t: tcl.find_word(t, "PAUSE", surround="<>")),
        "UNKNOWN_SEGMENT":
            lambda: text.apply(lambda t: tcl.find_word(t, "UNKNOWN_SEGMENT", surround="<>")),
        "invalid_audible_unintelligible":
            lambda: text.apply(lambda t: tcl.check_if_invalid(
                t, keys=["audible", "unintelligible"],
                surround="[]", invalid_sentence_from_tags_ratio=invalid_ratio)),
        "invalid_UNKNOWN_SEGMENT":
            lambda: text.apply(lambda t: tcl.check_if_invalid(
                t, keys=["UNKNOWN_SEGMENT"],
                surround="<>", invalid_sentence_from_tags_ratio=invalid_ratio)),
    }
    # The two language-aware checks are deliberately disjoint: Latin-script
    # languages have no Indic range to test, so they are covered by
    # check_nonnative instead of check_native_script_flag.
    if lang is not None:
        builders["nonnative_charecters"] = lambda: pd.Series(
            [tcl.check_nonnative(t, l) for t, l in zip(text, lang)], index=index)
        builders["native_script_mismatch"] = lambda: pd.Series(
            [tcl.check_native_script_flag(t, l) for t, l in zip(text, lang)],
            index=index)
    return builders


def run_content_checks(df: pd.DataFrame, cfg, text_column: str,
                       language_column: str = None,
                       key_column: str = None) -> List[Finding]:
    """Run every enabled check on `text_column` of `df`.

    Adds a `<check>_error` column per check and returns the findings. Row
    numbers in the findings are 1-based lines in the source file (header
    included), so they line up with what a spreadsheet shows.
    """
    findings: List[Finding] = []
    if text_column not in df.columns:
        return [Finding("ERROR", "text_column_missing",
                        message=f"Input has no '{text_column}' column; "
                                f"content checks skipped")]
    if df.empty:
        return [Finding("WARNING", "empty_input",
                        message="Input has no rows; content checks skipped")]

    has_key = bool(key_column) and key_column in df.columns
    check_words_limit = int(cfg.get("CONTENT_CHECKS", "check_words_limit",
                                    fallback="3"))
    invalid_ratio = float(cfg.get("CONTENT_CHECKS",
                                  "invalid_sentence_from_tags_ratio",
                                  fallback="0.5"))
    min_threshold = float(cfg.get("CONTENT_CHECKS",
                                  "batch_minimum_rejected_threshold",
                                  fallback="0.0"))

    text = df[text_column].fillna("").astype(str)
    lang = None
    if language_column and language_column in df.columns:
        lang = df[language_column].fillna("").astype(str)
    else:
        findings.append(Finding(
            "WARNING", "language_column_missing",
            message=(f"No '{language_column}' column; nonnative_charecters and "
                     f"native_script_mismatch skipped")))

    builders = build_check_map(text, lang, df.index,
                               check_words_limit, invalid_ratio)

    error_cols: Dict[str, pd.Series] = {}
    for name, build in builders.items():
        if not is_enabled(cfg, name):
            continue
        error_cols[name] = build().astype(bool)

    for check_name, series in error_cols.items():
        df[f"{check_name}_error"] = series
        for idx in series[series].index:
            findings.append(Finding(
                "ERROR", check_name,
                row=int(df.index.get_loc(idx)) + 2,
                key=str(df.loc[idx, key_column]) if has_key else "",
                column=text_column,
                message=f"{check_name} flagged",
            ))

    if is_enabled(cfg, "batch_minimum_acceptance") and error_cols:
        any_error = pd.DataFrame(error_cols).any(axis=1)
        pct = (any_error.sum() / len(any_error)) * 100 if len(any_error) else 0.0
        severity = "ERROR" if pct > min_threshold else "OK"
        findings.append(Finding(
            severity, "batch_minimum_acceptance",
            message=(f"{pct:.2f}% of rows have at least one content error "
                     f"({'>' if severity == 'ERROR' else '<='} threshold "
                     f"{min_threshold:.2f}%)"),
        ))
    return findings
