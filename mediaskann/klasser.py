"""Oversettelse fra detektorenes råklasser til våre hendelsestyper.

Lydklassene følger AudioSet-ontologien (som YAMNet klassifiserer mot),
bildeklassene følger COCO (som YOLO-modellene bruker). Begge tabellene er
rene navnelister, slik at de kan testes uten å laste ned en eneste modell.
"""

from __future__ import annotations

from .models import Hendelsestype

# --- Lyd: AudioSet-klasser som betyr «menneske» -----------------------------
MENNESKELYD_KLASSER = frozenset(
    {
        "speech",
        "male speech, man speaking",
        "female speech, woman speaking",
        "child speech, kid speaking",
        "conversation",
        "narration, monologue",
        "babbling",
        "speech synthesizer",
        "shout",
        "bellow",
        "whoop",
        "yell",
        "children shouting",
        "screaming",
        "whispering",
        "laughter",
        "baby laughter",
        "giggle",
        "snicker",
        "belly laugh",
        "chuckle, chortle",
        "crying, sobbing",
        "baby cry, infant cry",
        "whimper",
        "wail, moan",
        "sigh",
        "singing",
        "choir",
        "yodeling",
        "chant",
        "mantra",
        "male singing",
        "female singing",
        "child singing",
        "synthetic singing",
        "rapping",
        "humming",
        "groan",
        "grunt",
        "whistling",
        "breathing",
        "wheeze",
        "snoring",
        "gasp",
        "pant",
        "snort",
        "cough",
        "throat clearing",
        "sneeze",
        "sniff",
        "human voice",
        "human sounds",
        "human group actions",
        "applause",
        "cheering",
        "chatter",
        "crowd",
        "hubbub, speech noise, speech babble",
        "children playing",
        "clapping",
        "booing",
    }
)

# --- Lyd: AudioSet-klasser som betyr «dyr» ----------------------------------
DYRELYD_KLASSER = frozenset(
    {
        "animal",
        "domestic animals, pets",
        "dog",
        "bark",
        "yip",
        "howl",
        "bow-wow",
        "growling",
        "whimper (dog)",
        "canidae, dogs, wolves",
        "cat",
        "purr",
        "meow",
        "hiss",
        "caterwaul",
        "livestock, farm animals, working animals",
        "horse",
        "clip-clop",
        "neigh, whinny",
        "cattle, bovinae",
        "moo",
        "cowbell",
        "pig",
        "oink",
        "goat",
        "bleat",
        "sheep",
        "fowl",
        "chicken, rooster",
        "cluck",
        "crowing, cock-a-doodle-doo",
        "turkey",
        "gobble",
        "duck",
        "quack",
        "goose",
        "honk",
        "wild animals",
        "roaring cats (lions, tigers)",
        "roar",
        "bird",
        "bird vocalization, bird call, bird song",
        "chirp, tweet",
        "squawk",
        "pigeon, dove",
        "coo",
        "crow",
        "caw",
        "owl",
        "hoot",
        "bird flight, flapping wings",
        "rodents, rats, mice",
        "mouse",
        "chipmunk",
        "patter",
        "insect",
        "cricket",
        "mosquito",
        "fly, housefly",
        "buzz",
        "bee, wasp, etc.",
        "frog",
        "croak",
        "snake",
        "rattle",
        "whale vocalization",
    }
)

# --- Bilde: COCO-klasser ----------------------------------------------------
MENNESKE_BILDEKLASSER = frozenset({"person"})

DYR_BILDEKLASSER = frozenset(
    {
        "bird",
        "cat",
        "dog",
        "horse",
        "sheep",
        "cow",
        "elephant",
        "bear",
        "zebra",
        "giraffe",
    }
)


def _slå_opp(navn: str, tabell: dict[frozenset[str], Hendelsestype]) -> Hendelsestype | None:
    nøkkel = navn.strip().lower()
    for klasser, type_ in tabell.items():
        if nøkkel in klasser:
            return type_
    return None


def lydtype(klassenavn: str) -> Hendelsestype | None:
    """Hendelsestypen en AudioSet-klasse hører til, eller ``None``."""
    return _slå_opp(
        klassenavn,
        {
            MENNESKELYD_KLASSER: Hendelsestype.MENNESKESTEMME,
            DYRELYD_KLASSER: Hendelsestype.DYRELYD,
        },
    )


def bildetype(klassenavn: str) -> Hendelsestype | None:
    """Hendelsestypen en COCO-klasse hører til, eller ``None``."""
    return _slå_opp(
        klassenavn,
        {
            MENNESKE_BILDEKLASSER: Hendelsestype.MENNESKE_SYNLIG,
            DYR_BILDEKLASSER: Hendelsestype.DYR_SYNLIG,
        },
    )
