import re
from dataclasses import dataclass, field
from typing import List
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"   # block ingestion
    HIGH = "high"           # warn, still ingest
    MEDIUM = "medium"       # info only


@dataclass
class Finding:
    type: str
    severity: Severity
    match: str          # redacted version of the match
    line_hint: int      # approximate position in text
    description: str


@dataclass
class ScanResult:
    passed: bool                        # False = blocked
    findings: List[Finding] = field(default_factory=list)

    @property
    def critical(self): return [f for f in self.findings if f.severity == Severity.CRITICAL]
    @property
    def high(self): return [f for f in self.findings if f.severity == Severity.HIGH]
    @property
    def medium(self): return [f for f in self.findings if f.severity == Severity.MEDIUM]


# Pattern definitions: (name, regex, severity, description)
PATTERNS = [
    # Secrets — CRITICAL (block ingestion)
    (
        "aws_access_key",
        r"AKIA[0-9A-Z]{16}",
        Severity.CRITICAL,
        "AWS Access Key ID detected"
    ),
    (
        "aws_secret_key",
        r"(?i)aws.{0,20}secret.{0,20}['\"][0-9a-zA-Z/+]{40}['\"]",
        Severity.CRITICAL,
        "AWS Secret Access Key detected"
    ),
    (
        "generic_api_key",
        r"(?i)(api[_\-]?key|apikey|api[_\-]?secret)\s*[=:]\s*['\"]?[a-zA-Z0-9\-_]{20,}['\"]?",
        Severity.CRITICAL,
        "Generic API key or secret detected"
    ),
    (
        "private_key_header",
        r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
        Severity.CRITICAL,
        "Private key block detected"
    ),
    (
        "password_in_text",
        r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"]?.{6,}['\"]?",
        Severity.CRITICAL,
        "Hardcoded password detected"
    ),
    (
        "jwt_token",
        r"eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}",
        Severity.CRITICAL,
        "JWT token detected"
    ),
    (
        "groq_key",
        r"gsk_[a-zA-Z0-9]{50,}",
        Severity.CRITICAL,
        "Groq API key detected"
    ),
    (
        "openai_key",
        r"sk-[a-zA-Z0-9]{48}",
        Severity.CRITICAL,
        "OpenAI API key detected"
    ),

    # PII — HIGH (warn, allow ingest)
    (
        "credit_card",
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b",
        Severity.HIGH,
        "Credit card number detected"
    ),
    (
        "aadhaar_number",
        r"\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b",
        Severity.HIGH,
        "Aadhaar number detected"
    ),
    (
        "pan_number",
        r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",
        Severity.HIGH,
        "PAN card number detected"
    ),
    (
        "indian_phone",
        r"(?<!\d)(\+91[\-\s]?)?[6-9]\d{9}(?!\d)",
        Severity.HIGH,
        "Indian phone number detected"
    ),
    (
        "passport_number",
        r"\b[A-PR-WY][1-9]\d\s?\d{4}[1-9]\b",
        Severity.HIGH,
        "Passport number detected"
    ),

    # Info — MEDIUM
    (
        "email_address",
        r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b",
        Severity.MEDIUM,
        "Email address detected"
    ),
    (
        "ip_address",
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
        Severity.MEDIUM,
        "IP address detected"
    ),
]


def _redact(match_str: str) -> str:
    """Show first 4 chars + asterisks — enough to identify, not expose."""
    if len(match_str) <= 4:
        return "****"
    return match_str[:4] + "*" * min(len(match_str) - 4, 12)


def _find_line(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


class SecurityScanner:
    """
    Scans document text for secrets, PII, and sensitive data
    before it enters the vector store.
    """

    def scan(self, text: str, block_on_critical: bool = True) -> ScanResult:
        """
        Scan text for sensitive data.

        Args:
            text: Raw document text
            block_on_critical: If True, ScanResult.passed = False on any CRITICAL finding

        Returns:
            ScanResult with all findings
        """
        findings = []
        seen_matches = set()  # prevent duplicate reports

        for pattern_name, pattern, severity, description in PATTERNS:
            try:
                for match in re.finditer(pattern, text):
                    raw = match.group()
                    # Deduplicate
                    key = f"{pattern_name}:{raw}"
                    if key in seen_matches:
                        continue
                    seen_matches.add(key)

                    findings.append(Finding(
                        type=pattern_name,
                        severity=severity,
                        match=_redact(raw),
                        line_hint=_find_line(text, match.start()),
                        description=description,
                    ))
            except re.error:
                continue

        has_critical = any(f.severity == Severity.CRITICAL for f in findings)
        passed = not (block_on_critical and has_critical)

        return ScanResult(passed=passed, findings=findings)
# Prompt injection patterns
INJECTION_PATTERNS = [
    r"(?i)ignore (all |previous |above |prior )?instructions",
    r"(?i)forget (everything|all|what you)",
    r"(?i)you are now",
    r"(?i)act as (a|an|if)",
    r"(?i)disregard (your|all|previous)",
    r"(?i)new (role|persona|instructions|task|objective)",
    r"(?i)system\s*prompt",
    r"(?i)jailbreak",
    r"(?i)do anything now",
    r"(?i)(reveal|show|print|output|display).{0,30}(prompt|instructions|system)",
]


def detect_prompt_injection(text: str) -> dict:
    """
    Detect prompt injection attempts in query text.
    Returns dict with detected flag and matched patterns.
    """
    matches = []
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text):
            matches.append(pattern)

    return {
        "injection_detected": len(matches) > 0,
        "matched_patterns": len(matches),
    }