"""
language_to_script_mapping.py — Canonical language -> native-script mapping
for the TVA project.

Used by transcriptionCheckListFunction.check_native_script(), which validates
that a transcription uses only characters of the script expected for its
declared language. Script names here MUST match the names understood by
transcriptionCheckListFunction.get_unicode_list().

Scripts currently supported by get_unicode_list():
    devanagiri, bangla, telugu, kannada
Scripts that still need to be added to get_unicode_list() before the languages
below can be validated (Unicode block in parentheses):
    tamil        (0B80-0BFF)
    malayalam    (0D00-0D7F)
    gujarati     (0A80-0AFF)
    gurmukhi     (0A00-0A7F)
    perso-arabic (0600-06FF)
    meitei-mayek (ABC0-ABFF, + AAE0-AAFF extensions)

Latin / Roman-script languages (Northeast India) are NOT script-validated here;
they are handled by check_nonnative()'s bypass_lang_list and map to "latin".
"""

LANGUAGE_TO_SCRIPT_MAPPING = {
    # --- Devanagari ---
    "Hindi":       "devanagiri",
    "Nepali":      "devanagiri",
    "Marathi":     "devanagiri",
    "Rajasthani":  "devanagiri",
    "Halbi":       "devanagiri",
    "Maithili":    "devanagiri",

    # --- Bengali / Eastern Nagari (same 0980-09FF block) ---
    "Bengali":     "bangla",
    "Assamese":    "bangla",

    # --- Dravidian (existing sets) ---
    "Telugu":      "telugu",
    "Kannada":     "kannada",
    "Tulu":        "kannada",   # Tulu is written in the Kannada script
    "Konkani":     "devanagiri",   # TVA decision: Kannada-script Konkani

    # --- Scripts to be added to get_unicode_list() ---
    "Tamil":       "tamil",
    "Malayalam":   "malayalam",
    "Gujarati":    "gujarati",
    "Punjabi":     "gurmukhi",
    "Kashmiri":    "perso-arabic",   # TVA decision: Perso-Arabic (not Devanagari)
    "Manipuri":    "meitei-mayek",   # TVA decision: Meitei Mayek (not Bengali)

    # --- Latin / Roman script (handled via check_nonnative bypass) ---
    "Mizo":        "latin",
    "Karbi":       "latin",
    "Nyishi":      "latin",
    "Garo":        "latin",
    "Wancho":      "latin",
    "Nagamese":    "latin",
    "Chakma":      "latin",   # Chakma has its own script; treated as bypass for now

    # Fallback for any language not listed above.
    "default":     "devanagiri",
}


# Unicode code-point range(s) per script, as a list of (lo, hi) inclusive pairs.
# These are the character sets get_unicode_list() should build for each script.
# "latin" is listed for completeness but is not native-script-validated (its
# languages are bypassed in check_nonnative()).
SCRIPT_UNICODE_RANGES = {
    "devanagiri":   [(0x0900, 0x097F)],
    "bangla":       [(0x0980, 0x09FF)],
    "telugu":       [(0x0C00, 0x0C7F)],
    "kannada":      [(0x0C82, 0x0CF9)],
    "tamil":        [(0x0B80, 0x0BFF)],
    "malayalam":    [(0x0D00, 0x0D7F)],
    "gujarati":     [(0x0A80, 0x0AFF)],
    "gurmukhi":     [(0x0A00, 0x0A7F)],
    "perso-arabic": [(0x0600, 0x06FF)],
    "meitei-mayek": [(0xABC0, 0xABFF), (0xAAE0, 0xAAFF)],  # block + extensions
    "latin":        [(0x0041, 0x005A), (0x0061, 0x007A)],  # bypass; not validated
}

# Script-neutral characters allowed alongside any script (mirrors the
# common_chars used in get_unicode_list()).
COMMON_CHARS = [" ", ".", "?", "!", ",", "_", "-", "|"]

# --------------------------------------------------------------------------- #
# Script-neutral punctuation — allowed in ANY language's transcription.
# Reviewed and enumerated EXPLICITLY (not by Unicode category) so the set is
# auditable and stable. Anything outside this set that is not a native-script
# letter will be flagged by the native-script check.
#
# NOTE: the tag brackets ( ) [ ] < > { } are intentionally EXCLUDED. They are
# reserved tag syntax and are stripped before checking; a stray, unstripped one
# should still be caught.
# --------------------------------------------------------------------------- #
ALLOWED_PUNCTUATION = set(
    ".,?!;:-_'\"/"               # ASCII sentence punctuation
    "|"                          # legacy separator (kept from COMMON_CHARS)
    "।॥"               # ।  danda,  ॥  double danda
    "·"                     # ·  middle dot / interpunct
    "–—"               # –  en dash,  —  em dash
    "…"                     # …  ellipsis
    "‘’“”"   # ‘ ’ “ ”  smart / curly quotes
)

# Invisible format controls required for correct Indic shaping. Allowed
# everywhere; they carry no script identity of their own.
ALLOWED_FORMAT = {
    "​",   # ZERO WIDTH SPACE
    "‌",   # ZERO WIDTH NON-JOINER (ZWNJ)
    "‍",   # ZERO WIDTH JOINER (ZWJ)
}

# Everything that is script-neutral: punctuation + format + whitespace.
SCRIPT_NEUTRAL_CHARS = ALLOWED_PUNCTUATION | ALLOWED_FORMAT
