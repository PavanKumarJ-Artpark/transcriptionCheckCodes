from pathlib import Path
# jiwer / tqdm are needed only by check_cer_vs_decoded_transcripts() and
# score_with_lm(), which the content-check driver never calls. They are guarded
# so this repo installs with pandas + openpyxl alone; calling those two
# functions without the packages raises a clear NameError.
try:
    import jiwer
except ImportError:                                     # pragma: no cover
    jiwer = None
try:
    from tqdm import tqdm
except ImportError:                                     # pragma: no cover
    tqdm = None
import numpy as np
import pandas as pd
import re
import os
import sys

import language_to_script_mapping as _lsm


def get_text_without_brackets(text):
    text_wthout_brackets = re.sub(r'{[^}]*}','',text)
    text_wthout_brackets = re.sub("[\(\[].*?[\)\]]", "", text_wthout_brackets)
    text_wthout_brackets = re.sub('<[^>]+>', '', text_wthout_brackets)
    return text_wthout_brackets

def get_unicode_list(script):
    """
    Returns the list of unicode charecters for a given script
    
    Arguments
    ---------
    script : str
        The script for which the unicode charecters are required
    
    Returns
    -------
    charecters: list
        The list of charecters in the script
    """
    common_chars = [' ', '.', '?', '!', ',', '_', '-', '|']
    #https://unicode.org/charts/PDF/U0900.pdf
    signs = list(range(0X0900, 0X0980))
    devanagiri_charecters = [chr(c) for c in signs] 
    devanagiri_charecters = devanagiri_charecters + common_chars
    if script == "devanagiri":
        return devanagiri_charecters
    
    #https://unicode.org/charts/PDF/U0C00.pdf
    signs = list(range(0X0C00, 0X0C80))
    telugu_charecters = [chr(c) for c in signs] 
    telugu_charecters = telugu_charecters + common_chars
    if script == "telugu":
        return telugu_charecters
    
    #https://unicode.org/L2/L2003/03068-kannada.pdf
    signs = list(range(0X0C82, 0X0CFA))
    kannada_charecters = [chr(c) for c in signs]
    kannada_charecters = kannada_charecters + common_chars
    if script == "kannada":
        return kannada_charecters
    
    #https://unicode.org/charts/PDF/U0980.pdf
    signs = list(range(0X0980, 0X09FF))
    bengali_charecters = [chr(c) for c in signs]
    bengali_charecters = bengali_charecters + common_chars
    if script == "bangla":
        return bengali_charecters
    
    raise Exception(f"Script not found - {script}")
    
def find_word(text, search_string, surround=False):
    """
    Finds the word in the text
    
    Arguments
    ---------
    text : str
        The text to search for the word
    search_string : str
        The word to search
    surround : str
        The surrounding charecters of the word
    
    Returns
    -------
    output: str or None
        The word if it is not found, else None
    """
    pattern = r'\b' + re.escape(search_string) + r'\b'
    matches = re.findall(pattern, text)
    iter = re.finditer(pattern, text)
    matches_loc = [m.start(0) for m in iter]
    length = len(search_string)
    try:
        for match_idx in matches_loc:
            assert text[match_idx-1:match_idx+length+1] == list(surround)[0] + search_string + list(surround)[1]
    except:
        return True
    return False

def check_if_invalid(text, keys, surround,invalid_sentence_from_tags_ratio):
    """
    Checks if the word is invalid based on the ratio of the word to the total words
    
    Arguments
    ---------
    text : str
        The text to search for the word
    keys : list
        The list of words to search
    surround : str
        The surrounding charecters of the word
    
    Returns
    -------
    output: str or None
        The ratio percentage if it is invalid, else None
    """
    nums = 0
    text_without_key = text
    for key in keys:
        nums += len(re.findall("\\"+list(surround)[0] + key + list(surround)[1], text))
        text_without_key = text_without_key.replace(key, '')
    text_without_key = text_without_key.replace(surround, '')
    lens = len(text_without_key.split())
    try:
        percent = nums / lens
    except:
        percent = 1
    try:
        assert percent < invalid_sentence_from_tags_ratio
    except: 
        return True
    return False

def check_nonnative(text,lang):
    """
    Checks if the text has non-native charecters
    
    Arguments
    ---------
    text : str
        The text to search for the word
    
    Returns
    -------
    output: str or None
        The non-native charecter if it is invalid, else None
    """


    lang = lang.strip().lower()
    bypass_lang_list = ["chakma","garo", "wancho","Galo", "Nyishi", "Tagin", "english",
        "Kokborok","Hajong", "Angami", "Ao", "Chakhesang", "Lotha", "Nagamese", "Sumi", "Tenyidie", "rengma",
        'Yimchunger', 'Rongmei', 'Sangtam', 'Phom', 'Liangmei', 'Kuki', 'Zeme', 'NissiDafla', 'Idu mishmi','Karbi',
        'Mizo', 'Tangkhul','Liangmai', 'Vaiphei', 'Thadou'
    ]
    bypass_lang_list = [lang.strip().lower() for lang in bypass_lang_list]
    if lang in bypass_lang_list:
        return False

    text_wthout_brackets = get_text_without_brackets(text)
    string = re.findall('[a-zA-Z]',text_wthout_brackets)
    try:
        assert len(string) == 0
    except:
        return True
    return False

def check_bracket_structure(text):
    """Strict structural check on all bracket pairs ([], <>, {}).
    Returns True if any of these are present:
      - orphan closer (e.g. ']x[')
      - mismatched close (e.g. '[x>')
      - unclosed opener at end of string
      - nested or interleaved brackets (e.g. '[[x]]', '[<x>]')
      - empty bracket pair (e.g. '[]', '<>', '{}')

    Flat (non-nested) tags pass: 'a [unclear] b <PAUSE> c {music} d'.
    """
    pairs = {'[': ']', '<': '>', '{': '}'}
    closers = set(pairs.values())
    open_char = None
    open_pos = -1
    for i, ch in enumerate(text):
        if ch in pairs:
            if open_char is not None:
                return True   # nested: a bracket opened while another was open
            open_char = ch
            open_pos = i
        elif ch in closers:
            if open_char is None:
                return True   # orphan closer
            if pairs[open_char] != ch:
                return True   # mismatched close type
            if i == open_pos + 1:
                return True   # empty pair
            open_char = None
            open_pos = -1
    if open_char is not None:
        return True           # unclosed at end
    return False


def check_consecutive_duplicate_tag(text):
    """Returns True if a complete tag (<X>, [X], {X}) appears consecutively
    repeated, e.g. '<PAUSE><PAUSE>' or '[unintelligible] [unintelligible]'.
    Whitespace between repeats is tolerated.
    """
    pattern = re.compile(r"(<[^<>]+>|\[[^\[\]]+\]|\{[^{}]+\})\s*\1")
    return bool(pattern.search(text))


_TAG_SPACING_ALLOWED_ADJACENT = (
    set(" \t\n\r")                                       # whitespace
    | set("!\"#$%&'()*+,-./:;=?@\\^_`|~")                # ASCII punctuation (excluding < > [ ] { })
    | set("।॥–—…")                                       # common Indic / Unicode punctuation
)

def check_tag_spacing(text):
    """Returns True if any tag (<X>, [X], {X}) is directly glued to a
    letter/digit/mark with no whitespace or punctuation between.

    Tags at the start or end of the string are allowed.
    Punctuation immediately adjacent (e.g. '<PAUSE>.', 'कैसे? <PAUSE>') is allowed.
    Two tags directly abutting (e.g. '<PAUSE><UNKNOWN>') is FLAGGED.
    """
    pattern = re.compile(r"<[^<>]+>|\[[^\[\]]+\]|\{[^{}]+\}")
    for m in pattern.finditer(text):
        start, end = m.span()
        if start > 0 and text[start - 1] not in _TAG_SPACING_ALLOWED_ADJACENT:
            return True
        if end < len(text) and text[end] not in _TAG_SPACING_ALLOWED_ADJACENT:
            return True
    return False


# Major Indic Unicode blocks. Each value is (start, end) inclusive code points.
# https://unicode.org/charts/
_INDIC_SCRIPT_RANGES = {
    "devanagari": (0x0900, 0x097F),
    "bengali":    (0x0980, 0x09FF),
    "gurmukhi":   (0x0A00, 0x0A7F),
    "gujarati":   (0x0A80, 0x0AFF),
    "odia":       (0x0B00, 0x0B7F),
    "tamil":      (0x0B80, 0x0BFF),
    "telugu":     (0x0C00, 0x0C7F),
    "kannada":    (0x0C80, 0x0CFF),
    "malayalam":  (0x0D00, 0x0D7F),
}


def _script_of_char(ch):
    """Return script name, or None if the char is whitespace, ASCII digit,
    or punctuation (and therefore script-neutral)."""
    if ch.isspace():
        return None
    code = ord(ch)
    # ASCII punctuation / symbols
    if (0x0021 <= code <= 0x002F or
        0x003A <= code <= 0x0040 or
        0x005B <= code <= 0x0060 or
        0x007B <= code <= 0x007E):
        return None
    # ASCII digits
    if 0x0030 <= code <= 0x0039:
        return None
    # General Unicode punctuation block (en-dash, em-dash, ellipsis, etc.)
    if 0x2000 <= code <= 0x206F:
        return None
    # Standalone Indic punctuation: । (devanagari danda), ॥ (double danda)
    if code in (0x0964, 0x0965):
        return None
    # Latin-1 middle dot / interpunct (·) — script-neutral punctuation
    if code == 0x00B7:
        return None
    # ASCII / Latin-1 / Latin-Extended letters -> Latin
    if (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A):
        return "latin"
    if 0x00C0 <= code <= 0x024F:
        return "latin"
    # Indic scripts
    for name, (lo, hi) in _INDIC_SCRIPT_RANGES.items():
        if lo <= code <= hi:
            return name
    return "other"


def check_script_consistency(text):
    """Strip tags from text, classify remaining characters by Unicode script,
    return True if MORE than one script is present.

    Punctuation, whitespace, and ASCII digits are script-neutral and ignored.
    Indic-specific digits (e.g. ०१२३ in Devanagari, ௦௧௨ in Tamil) DO count
    toward their script, since they're a strong indicator of intent.

    Examples:
      'नमस्ते कैसे हो'        -> {devanagari}             -> False
      'வணக்கம் எப்படி'         -> {tamil}                  -> False
      'வணக்கம் कैसे'           -> {tamil, devanagari}      -> True   (mixed)
      'नमस्ते hello world'      -> {devanagari, latin}      -> True   (mixed)
      '[unintelligible]'        -> stripped to ''           -> False
      '12345 ?'                 -> {} (only digits/punct)   -> False
    """
    cleaned = get_text_without_brackets(text)
    scripts = set()
    for ch in cleaned:
        s = _script_of_char(ch)
        if s is not None:
            scripts.add(s)
    return len(scripts) > 1


def check_brackets(text, brackets):
    """
    Checks if the brackets are open and closed
    
    Arguments
    ---------
    text : str
        The text to search for the word
    brackets : list
        The list of brackets to search
    
    Returns
    -------
    output: str or None
        The bracket if it is invalid, else None
    """
    errors = ''
    for bracket in brackets:
        len1 = len(re.findall('\\'+bracket[0], text))
        len2 = len(re.findall(bracket[1], text))
        try:
            assert len1 == len2, f'{len1}, {len2}'
        except:
            errors+=bracket 
    if len(errors) > 0: return True
    return False

def check_numbers(text):
    """
    Returns True if the transcription contains any decimal digit
    AFTER bracket content is stripped. Catches both ASCII digits (0-9)
    and Indic digits (Devanagari ०-९, Tamil ௦-௯, Bengali ০-৯, etc.) — Python 3's
    `\\d` is Unicode-aware by default.

    Brackets are stripped first so digits inside legitimate tags (rare, but
    e.g. inside square brackets) don't false-positive on the body text.
    """
    cleaned = get_text_without_brackets(text)
    return bool(re.search(r'\d', cleaned))

def check_empty(text):
    """
    Checks if the text is missing entirely -- empty or nothing but whitespace.

    The caller coerces NULL to '' (fillna) before the checks run, so a NULL
    cell, an empty cell and a whitespace-only cell all land here. Every other
    content check is positive-detection (looks FOR something wrong), so each of
    them passes on an empty string -- this is the only check that catches it.

    Arguments
    ---------
    text : str
        The text to test

    Returns
    -------
    output: bool
        True if the text is empty/blank (invalid), else False
    """
    return str(text).strip() == ''

def check_words(text,check_words_limit):
    """
    Checks if the text has lesser words than the limit
    
    Arguments
    ---------
    text : str
        The text to search for the word
    
    Returns
    -------
    output: str or None
        The number of words if it is invalid, else None
    """
    text = get_text_without_brackets(text)
    lens = len(text.split(' '))
    try:
        assert lens >= check_words_limit 
    except:
        return True
    return False

def check_doublehyphen(text, sym):
    """
    Checks if the text has double hyphen
    
    Arguments
    ---------
    text : str
        The text to search for the word
    sym : str
        The symbol to search
    
    Returns
    -------
    output: str or None
        The symbol if it is invalid, else None
    """
    text = text.strip(sym)
    try:
        assert sym not in text
    except:
        return True
    return False


def check_purna_virma(text):
    """
    Checks if the text has purna viram
    
    Arguments
    ---------
    text : str
        The transcript to run the checks on
    
    Returns
    -------
    output: str or None
        The text wthout brackets if it is invalid, else None
    """
    text_wthout_brackets = get_text_without_brackets(text)
    if '।' in text_wthout_brackets.strip().strip('।'): 
        return True
    return False


def get_unicode_list(script):
    """
    Returns the list of unicode charecters for a given script
    
    Arguments
    ---------
    script : str
        The script for which the unicode charecters are required
    
    Returns
    -------
    charecters: list
        The list of charecters in the script
    """
    common_chars = [' ', '.', '?', '!', ',', '_', '-', '|']
    #https://unicode.org/charts/PDF/U0900.pdf
    signs = list(range(0X0900, 0X0980))
    devanagiri_charecters = [chr(c) for c in signs] 
    devanagiri_charecters = devanagiri_charecters + common_chars
    if script == "devanagiri":
        return devanagiri_charecters
    
    #https://unicode.org/charts/PDF/U0C00.pdf
    signs = list(range(0X0C00, 0X0C80))
    telugu_charecters = [chr(c) for c in signs] 
    telugu_charecters = telugu_charecters + common_chars
    if script == "telugu":
        return telugu_charecters
    
    #https://unicode.org/L2/L2003/03068-kannada.pdf
    signs = list(range(0X0C82, 0X0CFA))
    kannada_charecters = [chr(c) for c in signs]
    kannada_charecters = kannada_charecters + common_chars
    if script == "kannada":
        return kannada_charecters
    
    #https://unicode.org/charts/PDF/U0980.pdf
    signs = list(range(0X0980, 0X09FF))
    bengali_charecters = [chr(c) for c in signs]
    bengali_charecters = bengali_charecters + common_chars
    if script == "bangla":
        return bengali_charecters
    
    raise Exception(f"Script not found - {script}")


def check_native_script(
        sentence,
        language,
        language_to_script_mapping
    ):  
    """
    Checks if the sentence is in the native script
    
    Arguments
    ---------
    sentence : str
        The sentence to check
    language : str
        The language of the sentence
    
    Returns
    -------
    flag: str
        The flag if the sentence is invalid
    script: str
        The script of the sentence
    char: str
        The charecter in the sentence
    unicode: str
        The unicode of the charecter
    """
    language = language.strip().lower()
    if language not in language_to_script_mapping:
        script = language_to_script_mapping["default"]
    else:
        script = language_to_script_mapping[language]
    
    chars = get_unicode_list(script)
    current_chars = set(sentence)
    
    flag = False
    problematic_char = "NA"
    problematic_unicode = "NA"
    
    for char in current_chars:
        if char not in chars:
            flag = True
            problematic_char = char
            problematic_unicode = ord(char)
            break
    
    if len(current_chars) == 0:
        return True, script, "NA", "NA"

    return flag, script, problematic_char, problematic_unicode


def check_native_script_flag(text, language):
    """Pipeline check: True if the transcription contains a character that is NOT
    a letter of its declared language's native script and NOT a script-neutral
    character (allowed punctuation / zero-width format control).

    Tags are stripped first (same as every other content check). The expected
    script and the allowed-everywhere character set come from the consolidated
    language_to_script_mapping module. Languages whose script is 'latin' (the
    Roman-script NE languages, e.g. Mizo/Garo/Nagamese) are deliberately skipped
    here — they are validated by check_nonnative() instead — so this returns
    False for them.

    Returns a bool so it slots into check_tsv_df_content's check_builders exactly
    like check_nonnative.
    """
    lang_key = (language or "").strip()
    script = _lsm.LANGUAGE_TO_SCRIPT_MAPPING.get(
        lang_key, _lsm.LANGUAGE_TO_SCRIPT_MAPPING["default"])
    ranges = _lsm.SCRIPT_UNICODE_RANGES.get(script)
    if ranges is None or script == "latin":
        return False   # no validatable Indic script -> handled elsewhere

    neutral = _lsm.SCRIPT_NEUTRAL_CHARS
    for ch in get_text_without_brackets(text or ""):
        if ch.isspace() or ch in neutral:
            continue
        code = ord(ch)
        if any(lo <= code <= hi for lo, hi in ranges):
            continue
        return True
    return False


def check_word_to_duration(
        sentence,
        duration,
        word_to_duration_upper_threshold,
        word_to_duration_lower_threshold
    ):
    """
    Checks the word to duration ratio
    
    Arguments
    ---------
    sentence : str
        The sentence to check
    duration : float
        The duration of the sentence
    
    Returns
    -------
    flag: str
        The flag if the sentence is invalid
    ratio: float
        The ratio of the sentence
    """
    num_words = len(sentence.split())
    if num_words == 0:
        return True, 100
    ratio = duration / num_words
    if ratio > word_to_duration_upper_threshold:
        return True, ratio
    if ratio < word_to_duration_lower_threshold:
        return True, ratio
    return False, ratio

def check_repeats_in_sentence(
        sentence,
        repeats_in_sentence_min_num_words,
        repeats_in_sentence_threshold
    ):
    """
    Checks the repeats in the sentence
    
    Arguments
    ---------
    sentence : str
        The sentence to check
    
    Returns
    -------
    flag: str
        The flag if the sentence is invalid
    val: float
        The ratio of the sentence
    """
    num_words = len(sentence.split())
    num_unique_words = len(set(sentence.split()))
    
    if num_words < repeats_in_sentence_min_num_words:
        return False, np.nan
    val = num_words / num_unique_words
    if val > repeats_in_sentence_threshold:
        return True, val
    return False, val


def check_cer_vs_decoded_transcripts(sentence,asr_reference,CER_threshold):

    if asr_reference != "NA":
        if len(sentence.strip()) == 0:
            sentence = "E"
        if len(asr_reference.strip()) == 0:
            asr_reference = "E"
        cer = jiwer.cer(sentence, asr_reference)
        flag = False
        if cer > CER_threshold:
            flag = True
    
    elif asr_reference == "NA":
        cer = np.nan
        flag = False
    
    return flag, cer



def score_with_lm(
        sentence,
        lang,
        processTranscriptionObject,
        model,
        LM_supported_languages,
        LM_likelihood_threshold,
    ):  
    """
    Scores the sentence with the language model
    
    Arguments
    ---------
    sentence : str
        The sentence to score
    LM_stats : dict
        The language model statistics
    lang : str
        The language of the sentence
    model : dict
        The KenLM model
    
    Returns
    -------
    flag: str
        The flag if the sentence is invalid
    LM_stats: dict
        The language model statistics updated with the sentence statistics
    score: float
        The score of the sentence
    """
    lang = lang.strip().lower()
    if lang not in LM_supported_languages:
        return False, np.nan
    
    model = model[lang]
    oov_present = False
    
    words = sentence.split()
    processTranscriptionObject.LM_stats["words"].update(set(words))
    processTranscriptionObject.LM_stats["total_lines"] += 1
    words = ['<s>'] + words + ['</s>']
    for i, (prob, length, oov) in enumerate(model.full_scores(sentence)):
        if oov:
            processTranscriptionObject.LM_stats["OOV"].add(words[i+1])
            oov_present = True
    if oov_present:
        processTranscriptionObject.LM_stats["OOV_sentence"] += 1
    if "-" in sentence or '_' in sentence: 
        processTranscriptionObject.LM_stats["skipped_lines"] += 1  
        return False, np.nan
    score = model.score(sentence)
    if score < LM_likelihood_threshold:
        processTranscriptionObject.LM_stats["flagged_lines"] += 1
        return True, score
    return False, score




