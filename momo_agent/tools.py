from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .analyzer import MoMoAnalyzer

@dataclass
class ToolResult:
    ok: bool
    data: Any

def make_tools(analyzer: MoMoAnalyzer):
    """Return a dict of Python callables that can be exposed as LLM tools."""

    def get_overall_summary() -> Dict[str, Any]:
        """Return overall totals: income, expense, fees, net, tx_count."""
        return analyzer.summary()
    
    def get_period_summary(period: str, start: str | None = None, end: str | None = None) -> List[Dict[str, Any]]:
        df = analyzer.transactions()

        if start or end:
            df = analyzer.filter_range(start=start, end=end)

        tmp = MoMoAnalyzer(df)
        out = tmp.period_summary(period)
        return out.to_dict(orient="records")

    
    def get_top_spend_counterparties(n: int = 10) -> List[Dict[str, Any]]:
        """Top counterparties by amount spent (direction=out)."""
        df = analyzer.top_counterparties(direction="out", n=n)
        return df.to_dict(orient="records")
    
    def get_category_breakdown() -> List[Dict[str, Any]]:
        """Expense totals grouped by category."""
        df = analyzer.category_breakdown(direction="out")
        return df.to_dict(orient="records")
    
    def search_transactions(
            text: Optional[str] = None,
            start: Optional[str] = None,
            end: Optional[str] = None,
            direction: Optional[str] = None,
            category: Optional[str] = None,
            limit: int = 50,
        ) -> List[Dict[str, Any]]:
            """Search normalized transactions by simple filters."""
            df = analyzer.transactions()

            if start or end:
                df = analyzer.filter_range(start=start, end=end)

            if direction:
                df = df[df["direction"] == direction]

            if category:
                df = df[df["category"] == category]

            if text:
                t = text.lower()
                df = df[df["raw_sms"].str.lower().str.contains(t, na=False) |
                        df["counterparty"].fillna("").str.lower().str.contains(t, na=False)]
            df = df.sort_values("timestamp", ascending=False).head(int(limit))

            cols = ["timestamp","direction","category","counterparty","amount_rwf","fee_rwf","raw_type","txid"]
            out = df[cols].copy()

            out["timestamp"] = out["timestamp"].astype(str)
            out = out.where(out.notna(), None)

            return out.to_dict(orient="records")

    
    return {
        "get_overall_summary": get_overall_summary,
        "get_period_summary": get_period_summary,
        "get_top_spend_counterparties": get_top_spend_counterparties,
        "get_category_breakdown": get_category_breakdown,
        "search_transactions": search_transactions,
    }