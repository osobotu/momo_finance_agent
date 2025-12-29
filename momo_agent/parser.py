import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

from dateutil import parser as dtparser

# Helpers

## Regex
_AMOUNT_RE = re.compile(r"(?P<amt>\d[\d,]*(?:\.\d+)?)\s*RWF", re.IGNORECASE)
_FEE_RE = re.compile(r"Fee\s*[: ]\s*(?P<fee>\d[\d,]*(?:\.\d+)?)\s*RWF", re.IGNORECASE)
_BAL_RE = re.compile(r"Balance\s*[: ]\s*(?P<bal>\d[\d,]*(?:\.\d+)?)\s*RWF", re.IGNORECASE)
_DATETIME_RE = re.compile(r"(?P<dt>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})")
_TXID_RE = re.compile(r"TxId\s*[: ]\s*(?P<txid>[A-Za-z0-9]+)", re.IGNORECASE)
_FTID_RE = re.compile(r"FT\s*Id\s*[: ]\s*(?P<ftid>[A-Za-z0-9\-]+)", re.IGNORECASE)
_ETID_RE = re.compile(r"ET\s*Id\s*[: ]\s*(?P<etid>[A-Za-z0-9\-]+)", re.IGNORECASE)

## Counterparty patterns
_TO_RE = re.compile(r"\bto\s+(?P<name>[A-Za-z0-9 &\-\.\']+?)(?:\s*\(|\s+was\b|\s+with\b|\.|,)", re.IGNORECASE)
_FROM_RE = re.compile(r"\bfrom\s+(?P<name>[A-Za-z0-9 &\-\.\']+?)(?:\s*\(|\s+at\b|\.|,)", re.IGNORECASE)
_PHONE_RE = re.compile(r"\((?P<msisdn>\d{6,})\)")

def _to_int(x: Optional[str]) -> Optional[int]:
    if not x:
        return None
    x = x.replace(",", "")
    # Some messages may include decimals (rare) — keep as int RWF for reporting
    try:
        return int(float(x))
    except ValueError:
        return None


def _parse_datetime(text: str) -> Optional[datetime]:
    m = _DATETIME_RE.search(text)
    if m:
        try:
            return dtparser.parse(m.group("dt"))
        except Exception:
            return None
    return None

# Data model
@dataclass
class ParsedTransaction:
    msg_id: int
    raw_type: str
    timestamp: Optional[datetime]
    direction: str # "in", "out" or "unknown"
    category: str # "transfer", "merchant", "utilities", "cash" or "other"
    counterparty: Optional[str]
    msisdn: Optional[str]
    amount_rwf: Optional[str]
    fee_rwf: Optional[str]
    balance_rwf: Optional[str]
    txid: Optional[str]
    ftid: Optional[str]
    etid: Optional[str]
    raw_sms: str

    def to_row(self) -> Dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "raw_type": self.raw_type,
            "timestamp": self.timestamp.isoformat(sep=" ") if self.timestamp else None,
            "direction": self.direction,
            "category": self.category,
            "counterparty": self.counterparty,
            "msisdn": self.msisdn,
            "amount_rwf": self.amount_rwf,
            "fee_rwf": self.fee_rwf,
            "balance_rwf": self.balance_rwf,
            "txid": self.txid,
            "ftid": self.ftid,
            "etid": self.etid,
            "raw_sms": self.raw_sms,
        }

TYPE_MAP = {
    "sms_received_from_momo": ("in", "transfer"),
    "sms_transfer_to_number": ("out", "transfer"),
    "sms_payment_to_person": ("out", "transfer"),
    "sms_payment_to_merchant": ("out", "merchant"),
    "sms_cash_power": ("out", "utilities"),
    "sms_cash_tx": ("unknown", "cash"),
}

def parse_message(msg_id: int, raw_type: str, sms: str) -> ParsedTransaction:
    sms_norm = " ".join((sms or "").split())
    direction, category = TYPE_MAP.get(raw_type, ("unknown", "other"))

    amt = None
    m_amt = _AMOUNT_RE.search(sms_norm)
    if m_amt:
        amt = _to_int(m_amt.group("amt"))

    fee = None
    m_fee = _FEE_RE.search(sms_norm)
    if m_fee:
        fee = _to_int(m_fee.group("fee"))

    bal = None
    m_bal = _BAL_RE.search(sms_norm)
    if m_bal:
        bal = _to_int(m_bal.group("bal"))

    ts = _parse_datetime(sms_norm)

    txid = None
    m_txid = _TXID_RE.search(sms_norm)
    if m_txid:
        txid = m_txid.group("txid")

    ftid = None
    m_ftid = _FTID_RE.search(sms_norm)
    if m_ftid:
        ftid = m_ftid.group("ftid")

    etid = None
    m_etid = _ETID_RE.search(sms_norm)
    if m_etid:
        etid = m_etid.group("etid")

    
    # Counterparty
    counterparty = None
    msisdn = None

    if direction == "out":
        m_to = _TO_RE.search(sms_norm)
        if m_to:
            counterparty = m_to.group("name").strip(" .,-")
    elif direction == "in":
        m_from = _FROM_RE.search(sms_norm)
        if m_from:
            counterparty = m_from.group("name").strip(" .,-")
    else:
        # Try both
        m_to = _TO_RE.search(sms_norm)
        m_from = _FROM_RE.search(sms_norm)
        if m_to:
            counterparty = m_to.group("name").strip(" .,-")
        elif m_from:
            counterparty = m_from.group("name").strip(" .,-")

    m_phone = _PHONE_RE.search(sms_norm)
    if m_phone:
        msisdn = m_phone.group("msisdn")

    return ParsedTransaction(
        msg_id=msg_id,
        raw_type=raw_type,
        timestamp=ts,
        direction=direction,
        category=category,
        counterparty=counterparty,
        msisdn=msisdn,
        amount_rwf=amt,
        fee_rwf=fee,
        balance_rwf=bal,
        txid=txid,
        ftid=ftid,
        etid=etid,
        raw_sms=sms,
    )