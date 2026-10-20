"""Normalizzazione condivisa per nomi di calciatori e alias."""

import unicodedata


_TRASLITTERAZIONI = str.maketrans(
    {
        "ı": "i",
        "ł": "l",
        "đ": "d",
        "ð": "d",
        "ø": "o",
        "æ": "ae",
        "œ": "oe",
        "þ": "th",
        "ħ": "h",
    }
)


def normalizza_nome(valore: object) -> str:
    """Ignora accenti, maiuscole e separatori per confrontare varianti ortografiche."""
    if valore is None:
        return ""
    testo = str(valore).casefold().translate(_TRASLITTERAZIONI)
    decomposto = unicodedata.normalize("NFKD", testo)
    return "".join(
        carattere
        for carattere in decomposto
        if not unicodedata.combining(carattere) and carattere.isalnum()
    )
