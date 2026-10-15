"""
Rule-based query parser — reads the unambiguous filters off a query without an LLM:
genres, a decade or single year, a language, "rated above N".

Used to guess the plan before the LLM answers (speculator) and to keep filters working
when the LLM is unavailable (intent_classifier fallback). Anything ambiguous ("after 2015",
"highly rated", moods) is left unparsed rather than guessed.
"""
from __future__ import annotations

import re
from typing import List

from models.intent import QueryEntities
from tools.tmdb_tool import _GENRE_IDS

_GENRE_WORDS = {
    **{name: name for name in _GENRE_IDS},
    "sci fi": "sci-fi", "scifi": "sci-fi", "romantic": "romance", "animated": "animation",
    "comedies": "comedy", "thrillers": "thriller", "documentaries": "documentary",
    "westerns": "western", "mysteries": "mystery",
}

_LANGUAGES = {
    "hindi": "hi", "tamil": "ta", "telugu": "te", "malayalam": "ml", "kannada": "kn",
    "bengali": "bn", "marathi": "mr", "korean": "ko", "japanese": "ja", "chinese": "zh",
    "mandarin": "zh", "french": "fr", "spanish": "es", "german": "de", "italian": "it",
    "english": "en",
}

# Words that make a year relative ("after 2015") — the LLM resolves those, we don't guess
_RELATIVE_YEAR = re.compile(r"\b(after|before|since|between|until|till|onwards?|later|earlier|older|newer|to|through)\b")
_DECADE = re.compile(r"\b(?:19)?([5-9])0'?s\b|\b(20[0-2])0'?s\b")
_DECADE_WORDS = {"fifties": "5", "sixties": "6", "seventies": "7", "eighties": "8", "nineties": "9"}
_YEAR = re.compile(r"\b(19[2-9]\d|20[0-3]\d)\b")
_RATING = re.compile(r"\b(?:rated|rating|score)\s*(?:above|over|at least|of at least|>=?)\s*(\d(?:\.\d)?)\b")


# Matched against TMDB provider names after "+" becomes "plus", so these are TMDB's spellings
_PLATFORMS = {
    "netflix": "Netflix", "prime video": "Amazon Prime Video", "amazon prime": "Amazon Prime Video",
    "prime": "Amazon Prime Video", "disney+": "Disney Plus", "disney plus": "Disney Plus",
    "hotstar": "Hotstar", "hulu": "Hulu", "apple tv": "Apple TV Plus", "zee5": "Zee5",
    "sonyliv": "Sony Liv", "sony liv": "Sony Liv", "jiocinema": "JioCinema", "mubi": "MUBI",
    "peacock": "Peacock", "paramount+": "Paramount Plus", "paramount plus": "Paramount Plus",
}


# Words that carry no subject of their own: what's left of "best 90s crime movies from the
# nineties" once the filters are read off. Relative-year words count as filler too, so
# "horror movies after 2015" still reads as a filter-only query
_FILLER = frozenset(
    "a an the some any all me i im i'm we us you want wanna watch see find show give get list "
    "recommend suggest please good great best top new latest recent old classic movie movies film "
    "films flick flicks cinema from in of with and or on only just also instead rather but made "
    "released era decade decades year years language dubbed rated rating score above over at least "
    "more other others another different else something anything what about how maybe then now "
    "ones one them those these that this it is are there "
    "after before since between until till onward onwards later earlier older newer to through".split()
)


def _find_all(text: str, words: dict) -> List[str]:
    return [value for word, value in words.items() if re.search(rf"\b{re.escape(word)}s?\b", text)]


def subject_words(query: str) -> List[str]:
    """The words left once filters, platforms and filler are taken out: the query's own subject.

    The filter words also occur inside titles ("star wars", "the french connection",
    "2001: a space odyssey"), so a filter read off a query is only trustworthy when nothing
    else is left: "90s crime movies" → [], "star wars" → ["star"].
    """
    text = " ".join(query.lower().split())
    text = _RATING.sub(" ", text)
    text = _DECADE.sub(" ", text)
    text = _YEAR.sub(" ", text)
    for words in (_GENRE_WORDS, _LANGUAGES, _DECADE_WORDS):
        for word in sorted(words, key=len, reverse=True):    # "science fiction" before "fiction"
            text = re.sub(rf"\b{re.escape(word)}s?\b", " ", text)
    for word in sorted(_PLATFORMS, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", " ", text)
    return [w for w in re.findall(r"[a-z0-9']+", text) if w.strip("'") and w not in _FILLER]


def parse_entities(query: str) -> QueryEntities:
    """Extract only what can be read off the query without an LLM."""
    text = " ".join(query.lower().split()).rstrip("?!.")
    e = QueryEntities()

    e.genres = sorted(set(_find_all(text, _GENRE_WORDS)))

    languages = set(_find_all(text, _LANGUAGES))
    if len(languages) == 1:
        e.language = languages.pop()

    decades = _DECADE.findall(text) + [(d, "") for d in _find_all(text, _DECADE_WORDS)]
    years = _YEAR.findall(text)
    if not _RELATIVE_YEAR.search(text):
        if len(decades) == 1 and not years:
            short, long_ = decades[0]
            start = 1900 + int(short) * 10 if short else int(long_) * 10
            e.year_from, e.year_to = start, start + 9
        elif len(years) == 1 and not decades:
            e.year_from = e.year_to = int(years[0])

    rating = _RATING.search(text)
    if rating:
        e.min_rating = float(rating.group(1))
    return e


def parse_platforms(query: str) -> List[str]:
    """Streaming platforms named in the query ("only on netflix" → ["Netflix"])."""
    text = " ".join(query.lower().split())
    found = {name for word, name in _PLATFORMS.items() if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text)}
    return sorted(found)
