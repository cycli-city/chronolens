import json
import os
from datetime import datetime, timezone
from pathlib import Path


LOG_FILE = Path("./audit_log.jsonl")


class AuditLogger:
    """
    Append-only audit log. Every security-relevant event is
    written as a JSON line to audit_log.jsonl.
    One line per event — tamper-evident by nature (append-only).
    """

    def _write(self, event: dict):
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception:
            pass  # Never let logging crash the main flow

    def log_upload(self, document_id: str, version: int, filename: str,
                   ip: str, scan_passed: bool, findings_count: int):
        self._write({
            "action": "upload",
            "document_id": document_id,
            "version": version,
            "filename": filename,
            "ip": ip,
            "scan_passed": scan_passed,
            "findings_count": findings_count,
        })

    def log_query(self, action: str, document_id: str, ip: str,
                  threat_detected: bool = False):
        self._write({
            "action": action,
            "document_id": document_id,
            "ip": ip,
            "threat_detected": threat_detected,
        })

    def log_security_block(self, reason: str, ip: str, detail: str = ""):
        self._write({
            "action": "security_block",
            "reason": reason,
            "ip": ip,
            "detail": detail[:200],
        })

    def get_recent(self, n: int = 50) -> list:
        """Read the last n audit entries."""
        if not LOG_FILE.exists():
            return []
        try:
            lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
            return [json.loads(l) for l in lines[-n:]]
        except Exception:
            return []