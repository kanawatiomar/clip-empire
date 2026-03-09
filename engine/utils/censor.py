"""censor.py - Profanity filter for YouTube-safe titles and descriptions.

Replaces curse words with censored versions (e.g., "f**k") to avoid
YouTube content warnings and channel strikes.
Ported from Arc Highlightz standalone engine.
"""

import re

# Map of curse words -> censored replacement (longest first to avoid partial matches)
CENSOR_MAP = {
    "motherfucker": "m**********r", "motherfucking": "m***********g",
    "motherfuckers": "m**********s", "motherfucked": "m*********d",
    "motherfuck": "m*********k", "muthafucka": "m*********a",
    "muthafucker": "m**********r",
    "fuckinggg": "f*******", "fuckingg": "f******", "fucking": "f*****g",
    "fuuuuuck": "f******k", "fuuuuck": "f*****k", "fuuuck": "f****k",
    "fuuck": "f***k", "fucks": "f***s", "fucked": "f****d",
    "fucker": "f****r", "fuckers": "f*****s", "fuckin": "f****n",
    "fuck": "f**k",
    "bullshitting": "b*********g", "bullshitter": "b*********r",
    "bullshitted": "b*********d", "bullshitters": "b**********s",
    "shithead": "s*******d", "shitshow": "s*******w",
    "shitting": "s*******g", "shitty": "s****y", "shitter": "s*****r",
    "shits": "s***s", "shit": "s**t",
    "asshole": "a*****e", "assholes": "a*****es", "asses": "a***s",
    "ass": "a**",
    "bitch": "b***h", "bitches": "b*****s", "bitching": "b*****g",
    "bastard": "b*****d", "bastards": "b*****ds",
    "damn": "d***", "goddamn": "g*****n",
    "crap": "c**p",
    "hell": "h**l",
    "pissed": "p***ed", "piss": "p**s",
    "whore": "w***e", "whores": "w***es",
    "slut": "s**t", "sluts": "s**ts",
    "dick": "d**k", "dicks": "d**ks",
    "cock": "c**k", "cocks": "c**ks",
    "pussy": "p***y",
    "cunt": "c**t", "cunts": "c**ts",
    "nigga": "n***a", "nigger": "n*****", "niggas": "n***as",
    "retard": "r*****", "retarded": "r*******",
    "faggot": "f*****", "fag": "f*g",
}

# Build sorted pattern (longest first to avoid partial matches)
_SORTED_WORDS = sorted(CENSOR_MAP.keys(), key=len, reverse=True)
_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in _SORTED_WORDS) + r')\b',
    re.IGNORECASE
)


def censor_text(text: str) -> str:
    """Replace profanity with censored versions. Case-insensitive, preserves surrounding text."""
    if not text:
        return text

    def replace_match(m: re.Match) -> str:
        word = m.group(0).lower()
        censored = CENSOR_MAP.get(word, word)
        # Preserve capitalization of first letter
        if m.group(0)[0].isupper():
            censored = censored.capitalize()
        return censored

    return _PATTERN.sub(replace_match, text)


def is_clean(text: str) -> bool:
    """Return True if text contains no censored words."""
    return _PATTERN.search(text) is None


if __name__ == "__main__":
    tests = [
        "Shroud goes absolutely insane",
        "what the fuck was that play",
        "Tfue says holy shit after clutching",
        "This is bullshit, he's hacking",
        "Clean title with no swearing",
    ]
    for t in tests:
        print(f"  IN:  {t}")
        print(f"  OUT: {censor_text(t)}")
        print()
