# transcriptionCheck

Content checks for transcription text. Point it at a file, name the column
holding the transcription, get an xlsx report of everything that looks wrong
with the text — unclosed tags, tags glued to words, digits left unspelt,
characters outside the language's script, and so on.

Project-agnostic: every column name, threshold and check is configuration, so
the same tool runs over any project's TSV, CSV or Excel export. The code carries
no project assumptions; `config.cfg` is where the project lives. It ships
pointed at a QC review export — change the column names under `[INPUT]` for
anything else.

**No database, no email, no bucket.** It reads local files and writes one local
report. Nothing else.

## Install

```bash
pip install -r requirements.txt      # pandas + openpyxl
```

## Run

```bash
# a single file
python transcriptionCheck.py --input batch.tsv --text-column transcription

# a folder — every .tsv/.csv/.txt/.xlsx in it, each on its own report sheet
python transcriptionCheck.py --input someFolder/

# include sub-folders
python transcriptionCheck.py --input someFolder/ --recursive

# console only, no report file
python transcriptionCheck.py --input batch.tsv --print-only
```

With no `--input` it uses `[INPUT] path` from `config.cfg`. Exit code is 0 when
nothing is flagged, 1 when any check raises an ERROR.

Flags: `--input`, `--text-column`, `--language-column`, `--key-column`, `--sep`,
`--recursive`, `--out`, `--print-only`, `--config`. Each defaults to its
`config.cfg` entry, so set the config once for a project and just run it.

## The checks

| check | flags a row when |
| --- | --- |
| `transcript_is_empty` | the text is blank or whitespace-only |
| `number_of_words_lt_threshold` | fewer than `check_words_limit` words (off by default) |
| `transcript_has_numbers` | digits are left in the text instead of being spelt out |
| `brackets_dont_have_open_close` | a `[ ]`, `< >` or `{ }` is never closed |
| `bracket_structure_invalid` | tags are malformed or crossed rather than nested |
| `consecutive_duplicate_tag` | the same tag appears twice in a row |
| `tag_spacing_missing` | a tag is glued to a word with no space — `<noise>આ` — or two tags abut |
| `script_inconsistency` | more than one Indic script appears in one line |
| `inaudible`, `unintelligible` | the word appears bare, not wrapped as `[inaudible]` |
| `PAUSE`, `UNKNOWN_SEGMENT` | the word appears bare, not wrapped as `<PAUSE>` |
| `nonnative_charecters` | Latin letters appear outside `{ }` |
| `native_script_mismatch` | a character falls outside the declared language's script |
| `batch_minimum_acceptance` | the share of failing rows exceeds the threshold |

`nonnative_charecters` and `native_script_mismatch` are deliberately disjoint:
Latin-script languages (Mizo, Garo, Nagamese …) have no Indic range to test
against, so they are covered by the first and skipped by the second. Both need
the language column; without it they are skipped with a warning and every other
check still runs.

Toggle any check under `[CHECKS]`. Thresholds live under `[CONTENT_CHECKS]`.
`language_to_script_mapping.py` holds the language → script table, the Unicode
ranges and the script-neutral character set — edit it to change what counts as
in-script.

## Which rows get checked

Two optional gates, both in `[INPUT]`:

**The condition gate.** `condition_column` / `condition_value` check a row only
when that column does *not* equal that value. Useful when only some rows carry
text worth validating — the shipped config uses it for a QC review export, where
the reviewer writes a corrected transcription only when the original was wrong:

```ini
condition_column = Does the transcribed text exactly match the audio?
condition_value = yes
```

Blank out `condition_column` to check every row. If the named column is missing
from a file the runner warns and checks everything rather than skipping it
silently.

**The blank gate.** Rows whose text is blank are skipped rather than each being
reported as empty — set `skip_blank_rows = false` to check them too.
`blank_values` lists extra placeholder strings (`nan`, `none`, `null`, `na`)
treated as blank.

## The report

`results/TranscriptionCheckReport_<ts>.xlsx` — one report per run, covering
every file checked:

| sheet | contents |
| --- | --- |
| `Summary` | one row per input file: `file / sheet / status / errors / warnings / total` |
| `<n>_<file>` | findings: `severity / check / row / key / column / message` |
| `<n>_<file>_rows` | every input row plus one boolean `<check>_error` column per check |

`row` is the 1-based line number in the source file, header included, so it
matches what a spreadsheet shows. `key` is the `key_column` value when one is
set. ERROR / WARNING / OK rows are filled red / amber / green.

Sheet names are numbered and keep the **tail** of the file name: Excel caps
names at 31 characters, and files in a batch often differ only in their last few
characters (`..._V1`, `..._V2`, `..._V3`), so trimming from the front would give
every file the same sheet name and silently collapse them onto one sheet.

Each file is checked independently — there is no cross-file comparison, so a
folder can hold unrelated exports.

## Layout

| file | role |
| --- | --- |
| `transcriptionCheck.py` | CLI: reads the input, runs the checks, writes the report |
| `contentChecks.py` | the check driver — which checks run, in what order, and the findings |
| `transcriptionCheckListFunction.py` | the individual check functions |
| `language_to_script_mapping.py` | language → script, Unicode ranges, script-neutral characters |
| `config.cfg` | input columns, output directory, thresholds, check toggles |

`jiwer` and `tqdm` are imported defensively in
`transcriptionCheckListFunction.py`: they are needed only by two ASR/LM scoring
helpers nothing here calls, so the install stays at pandas plus openpyxl.
