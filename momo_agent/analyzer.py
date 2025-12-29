import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import pandas as pd
from .parser import parse_message, ParsedTransaction

@dataclass
class Report:
    title: str
    markdown: str

class MoMoAnalyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

        # Normalize timestamp to pandas datetime
        self.df["timestamp"] = pd.to_datetime(self.df["timestamp"], errors="coerce")
        self.df["date"] = self.df["timestamp"].dt.date
        self.df["month"] = self.df["timestamp"].dt.to_period("M").astype(str)
        self.df["week"] = self.df["timestamp"].dt.to_period("W").astype(str)
        self.df["year"] = self.df["timestamp"].dt.year

        # Convert amount columns to numeric
        for col in ["amount_rwf", "fee_rwf", "balance_rwf"]:
            self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

    @staticmethod
    def from_json(path: str | Path) -> "MoMoAnalyzer":
        path = Path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows: List[Dict[str, Any]] = []
        for m in payload.get("messages", []):
            pt: ParsedTransaction = parse_message(
                msg_id=int(m.get("id")),
                raw_type=str(m.get("type", "unknown")),
                sms=str(m.get("sms", "")),
            )
            rows.append(pt.to_row())
        df = pd.DataFrame(rows)
        return MoMoAnalyzer(df)
    
    def transactions(self) -> pd.DataFrame:
        return self.df.copy()
    
    def _split_income_expense(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        income = self.df[self.df["direction"] == "in"].copy()
        expense = self.df[self.df["direction"] == "out"].copy()
        return income, expense
    
    def summary(self) -> Dict[str, Any]:
        income, expense = self._split_income_expense()

        total_in = float(income["amount_rwf"].sum(skipna=True))
        total_out = float(expense["amount_rwf"].sum(skipna=True))
        total_fees = float(self.df["fee_rwf"].sum(skipna=True))
        net = total_in - total_out - total_fees

        return {
            "total_in_rwf": int(total_in),
            "total_out_rwf": int(total_out),
            "total_fees_rwf": int(total_fees),
            "net_rwf": int(net),
            "tx_count": int(len(self.df)),
        }
    
    def period_summary(self, period: str = "month") -> pd.DataFrame:
        if period not in {"week", "month", "year"}:
            raise ValueError("period must be one of: week, month, year")

        df = self.df.copy()

        df["income_amt"] = df["amount_rwf"].where(df["direction"] == "in", 0)
        df["expense_amt"] = df["amount_rwf"].where(df["direction"] == "out", 0)
        df["fee_amt"] = df["fee_rwf"].fillna(0)

        out = (
            df.groupby(period, dropna=False)
            .agg(
                tx_count=("msg_id", "count"),
                income_rwf=("income_amt", "sum"),
                expense_rwf=("expense_amt", "sum"),
                fees_rwf=("fee_amt", "sum"),
            )
            .reset_index()
        )

        out["net_rwf"] = out["income_rwf"] - out["expense_rwf"] - out["fees_rwf"]

        for c in ["income_rwf", "expense_rwf", "fees_rwf", "net_rwf"]:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype(int)

        out["tx_count"] = out["tx_count"].astype(int)
        return out.sort_values(period)

    
    def top_counterparties(self, direction: str = "out", n: int = 10) -> pd.DataFrame:
        df = self.df[self.df["direction"] == direction].copy()
        df["counterparty"] = df["counterparty"].fillna("Unknown")
        out = df.groupby("counterparty")["amount_rwf"].sum().sort_values(ascending=False).head(n).reset_index()
        out["amount_rwf"] = out["amount_rwf"].fillna(0).astype(int)
        return out
    
    def category_breakdown(self, direction: str = "out") -> pd.DataFrame:
        df = self.df[self.df["direction"] == direction].copy()
        df["category"] = df["category"].fillna("other")
        out = df.groupby("category")["amount_rwf"].sum().sort_values(ascending=False).reset_index()
        out["amount_rwf"] = out["amount_rwf"].fillna(0).astype(int)
        return out
    
    def filter_range(self, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        df = self.df.copy()
        if start:
            start_dt = pd.to_datetime(start)
            df = df[df["timestamp"] >= start_dt]
        if end:
            end_dt = pd.to_datetime(end)
            df = df[df["timestamp"] <= end_dt]
        return df
    
    def render_report(self, period: str) -> Report:
        s = self.summary()
        ps = self.period_summary(period)
        top_out = self.top_counterparties("out", 8)
        cats_out = self.category_breakdown("out")

        md = []
        md.append(f"# MoMo Finance Report ({period.title()})\n")
        md.append("## Overall\n")
        md.append(f"- Transactions: **{s['tx_count']}**\n")
        md.append(f"- Income: **{s['total_in_rwf']:,} RWF**\n")
        md.append(f"- Expense: **{s['total_out_rwf']:,} RWF**\n")
        md.append(f"- Fees: **{s['total_fees_rwf']:,} RWF**\n")
        md.append(f"- Net: **{s['net_rwf']:,} RWF**\n")

        md.append("\n## By period\n")
        md.append(ps.to_markdown(index=False))
        md.append("\n\n## Top spend counterparties\n")
        md.append(top_out.to_markdown(index=False))
        md.append("\n\n## Expense by category\n")
        md.append(cats_out.to_markdown(index=False))

        return Report(title=f"MoMo Finance Report ({period})", markdown="\n".join(md) + "\n")
