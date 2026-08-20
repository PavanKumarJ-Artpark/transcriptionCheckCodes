# transcriptionCheck

The TVA transcription content checks, standalone. Point it at a file, name the
column holding the transcription, get an xlsx report of everything that looks
wrong with the text.

**No database, no email, no bucket.** It reads a local file and writes a local
report. Nothing else.

## Install

```bash
pip install -r requirements.txt      # pandas + openpyxl
```

## Run

```bash
# a single file
python transcriptionCheck.py --input delivery_V1.tsv

# a whole folder — every .tsv/.csv/.txt/.xlsx inside it
python transcriptionCheck.py --input someFolder/

# name the column to check
python transcriptionCheck.py --input batch.tsv --text-column transcription

# console only, no report file
python transcriptionCheck.py --input batch.tsv --print-only
```

With no `--input` it uses `[INPUT] path` from `config.cfg`. Exit code is 0 when
nothing is flagged, 1 when any check raises an ERROR.

Flags: `--input`, `--text-column`, `--language-column`, `--key-column`, `--sep`,
`--out`, `--print-only`, `--config`. Each defaults to its `config.cfg` entry.

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
the language column; without it they are skipped with a warning.

Every check is toggled under `[CHECKS]` in `config.cfg`. Thresholds live under
`[CONTENT_CHECKS]`.

## Which rows get checked

By default rows whose text is blank are skipped rather than each being reported
as empty — set `skip_blank_rows = false` to check them too. `blank_values` lists
extra placeholder strings (`nan`, `none`, `null`, `na`) treated as blank.

## The report

`results/TranscriptionCheckReport_<ts>.xlsx`:

| sheet | contents |
| --- | --- |
| `Summary` | one row per input file: `file / sheet / status / errors / warnings / total` |
| `<n>_<file>` | findings: `severity / check / row / key / column / message` |
| `<n>_<file>_rows` | every input row plus one boolean `<check>_error` column per check |

`row` is the 1-based line number in the source file, header included, so it
matches what a spreadsheet shows. ERROR / WARNING / OK rows are filled red /
amber / green.

Sheet names are numbered and keep the **tail** of the file name: Excel caps
names at 31 characters, and delivery files often differ only in their last few
characters (`..._V1`, `..._V2`, `..._V3`), so trimming from the front would give
every file the same sheet name and silently collapse them onto one sheet.

## Layout

| file | role |
| --- | --- |
| `transcriptionCheck.py` | CLI: reads the input, runs the checks, writes the report |
| `contentChecks.py` | the check driver — which checks run, in what order, and the findings |
| `transcriptionCheckListFunction.py` | the individual check functions |
| `language_to_script_mapping.py` | language → script, Unicode ranges, script-neutral characters |
| `config.cfg` | input columns, output directory, thresholds, check toggles |

## Relationship to the TVA pipeline

`transcriptionCheckListFunction.py` and `language_to_script_mapping.py` are
copies of the modules in `tvaExperiment/tvaDeployment/codes`, and
`contentChecks.py` is that pipeline's `check_tsv_df_content` with the database
coupling removed. The checks and their order are unchanged, so a row that fails
here fails there too.

Because they are copies, a rule change on either side has to be carried across
by hand. The `jiwer` and `tqdm` imports are guarded here: they are only needed by
two ASR/LM scoring helpers this repo never calls, so the install stays at pandas
plus openpyxl.
