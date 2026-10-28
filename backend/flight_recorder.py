"""
AQUILA Cryptographic Flight Recorder (SHA-256 Immutable Audit Log)
==================================================================
Blockchain-style tamper-evident ledger for telemetry, valve actuations,
and automated threat mitigation decisions.
"""

import hashlib
import json
from backend.config import json_sanitize


class AuditLog:
    """Hash-chained flight recorder: editing any past entry breaks every subsequent hash."""

    def __init__(self):
        self.chain = []

    @staticmethod
    def _hash(body):
        serialized = json.dumps(body, sort_keys=True, default=json_sanitize).encode()
        return hashlib.sha256(serialized).hexdigest()

    def add(self, tick, kind, payload):
        """Appends a new event cryptographically linked to the previous block hash."""
        prev = self.chain[-1]["hash"] if self.chain else "0" * 64
        body = dict(
            i=len(self.chain),
            tick=tick,
            kind=kind,
            payload=payload,
            prev=prev
        )
        self.chain.append(dict(body, hash=self._hash(body)))

    def verify(self):
        """Verifies the integrity of the ledger. Returns (is_valid, broken_block_index)."""
        prev = "0" * 64
        for e in self.chain:
            body = {k: e[k] for k in ("i", "tick", "kind", "payload", "prev")}
            if e["prev"] != prev or self._hash(body) != e["hash"]:
                return False, e["i"]
            prev = e["hash"]
        return True, None
