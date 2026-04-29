"""Sicherheits-Helpers: Password-Hashing.

Senior-Regel: NIEMALS Passwoerter im Klartext speichern - immer hashen.
NIEMALS eigene Hashing-Algorithmen verwenden - immer geprueftes wie bcrypt.
NIEMALS schwache Hashes (MD5, SHA1) - die sind in Sekunden geknackt.

bcrypt ist bewusst LANGSAM (~250ms pro Hash) - das schuetzt vor Brute-Force.
Der 'work factor' (Standard 12) erhoeht die Kosten exponentiell.
"""

from __future__ import annotations

import bcrypt


def hash_password(plain_password: str) -> str:
    """Hasht ein Passwort mit bcrypt.

    bcrypt erzeugt automatisch ein Salt - kein eigenes Salt-Management noetig.
    Der zurueckgegebene String enthaelt Algorithmus, Cost-Factor und Salt.
    """
    if not plain_password:
        raise ValueError("Passwort darf nicht leer sein.")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Prueft, ob ein Klartext-Passwort zu einem bcrypt-Hash passt.

    constant-time-Vergleich (verhindert Timing-Attacks).
    """
    if not plain_password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        # bcrypt wirft bei korruptem Hash - wir behandeln das als "kein Match".
        return False
