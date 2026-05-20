from __future__ import annotations

import hashlib
from pathlib import Path


def cert_fingerprint_sha256(cert_path: Path) -> str:
    digest = hashlib.sha256(Path(cert_path).read_bytes()).hexdigest().upper()
    return ":".join(digest[i:i + 2] for i in range(0, len(digest), 2))
