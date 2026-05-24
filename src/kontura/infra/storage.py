"""Datei-Speicher-Abstraktion fuer Kontura AI.

Senior-Pattern: Protocol + konkrete Implementierung
====================================================
FileStorage ist ein Protocol (strukturelles Subtyping), damit wir spaeter
ohne Interface-Aenderungen S3Storage, GCSStorage etc. hinzufuegen koennen.
Die DI-Funktion in dependencies.py entscheidet, welche Implementierung genutzt wird.

Phase G2.0: Nur LocalFilesystemStorage.
Phase G2.x: S3Storage kann hier eingefuegt werden, ohne Router oder Repository
zu aendern.

TODO (future): Virus-Scan-Hook vor save() einhaengen (ClamAV o.ae.).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol, runtime_checkable

import aiofiles
import aiofiles.os

from kontura.core.config import settings
from kontura.core.exceptions import NotFoundError


@runtime_checkable
class FileStorage(Protocol):
    """Protokoll fuer den Datei-Speicher.

    Alle Methoden sind async - damit S3 spaeter ohne Umbau passt.
    storage_path ist ein opaker relativer Key - der Caller weiss nichts ueber
    die Verzeichnisstruktur oder den Bucket.
    """

    async def save(self, tenant_id: str, sha256: str, content: bytes) -> str:
        """Speichert Dateiinhalt und gibt den storage_path zurueck.

        Der storage_path ist ein relativer, opaker Schluessel.
        Idempotent: wird dieselbe sha256 zweimal geschrieben, ueberschreibt
        der zweite Write den ersten (der Inhalt ist identisch - dedup greift
        auf DB-Ebene, aber Storage bleibt konsistent).
        """
        ...

    async def load(self, storage_path: str) -> bytes:
        """Laedt den Dateiinhalt anhand des storage_path.

        Wirft NotFoundError wenn die Datei fehlt.
        """
        ...

    async def delete(self, storage_path: str) -> None:
        """Loescht die Datei. Idempotent: kein Fehler wenn bereits weg."""
        ...


class LocalFilesystemStorage:
    """Lokale Dateisystem-Implementierung des FileStorage-Protokolls.

    Layout: {base_dir}/{tenant_id}/{sha256[:2]}/{sha256}
    - sha256[:2] als Unterverzeichnis verhindert Inodes-Flooding bei vielen Dateien
      (ahnlich wie git objects oder npm cache)
    - tenant_id als Top-Level-Verzeichnis = physische Tenant-Isolation

    base_dir kommt aus settings.invoice_files_dir, Standard: ./backend-data/invoice-files
    """

    def __init__(self, base_dir: str | None = None) -> None:
        self._base = Path(base_dir or settings.invoice_files_dir).resolve()

    def _path_for(self, tenant_id: str, sha256: str) -> Path:
        """Berechnet den absoluten Dateipfad fuer einen Datei-Hash."""
        return self._base / tenant_id / sha256[:2] / sha256

    def _storage_path(self, tenant_id: str, sha256: str) -> str:
        """Gibt den relativen storage_path zurueck (opak fuer den Caller)."""
        return f"{tenant_id}/{sha256[:2]}/{sha256}"

    async def save(self, tenant_id: str, sha256: str, content: bytes) -> str:
        """Speichert Dateiinhalt auf dem lokalen Dateisystem.

        Erstellt fehlende Verzeichnisse automatisch (exist_ok=True).
        Gibt den relativen storage_path zurueck.
        """
        dest = self._path_for(tenant_id, sha256)
        await aiofiles.os.makedirs(str(dest.parent), exist_ok=True)
        async with aiofiles.open(dest, "wb") as f:
            await f.write(content)
        return self._storage_path(tenant_id, sha256)

    async def load(self, storage_path: str) -> bytes:
        """Laedt Datei vom lokalen Dateisystem.

        Wirft NotFoundError wenn die Datei nicht existiert.
        """
        full_path = self._base / storage_path
        if not full_path.exists():
            raise NotFoundError(f"Datei nicht gefunden: {storage_path}")
        async with aiofiles.open(full_path, "rb") as f:
            data: bytes = await f.read()
        return data

    async def delete(self, storage_path: str) -> None:
        """Loescht Datei idempotent - kein Fehler wenn bereits weg."""
        full_path = self._base / storage_path
        try:
            await aiofiles.os.remove(str(full_path))
        except FileNotFoundError:
            pass  # Idempotent: bereits weg ist OK


def _verify_sha256(content: bytes, sha256: str) -> bool:
    """Prueft ob der SHA-256-Hash des Inhalts mit dem erwarteten Hash uebereinstimmt."""
    return hashlib.sha256(content).hexdigest() == sha256
