"""Sicherheits-Helpers fuer Kontura AI."""

from __future__ import annotations

import bcrypt

from kontura.core.security.disposable_emails import is_disposable_email


def hash_password(plain_password: str) -> str:
    """Hasht ein Passwort mit bcrypt."""
    if not plain_password:
        raise ValueError("Passwort darf nicht leer sein.")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Prueft, ob ein Klartext-Passwort zu einem bcrypt-Hash passt."""
    if not plain_password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


__all__ = ["hash_password", "verify_password", "is_disposable_email"]
