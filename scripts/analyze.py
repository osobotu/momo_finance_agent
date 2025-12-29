import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from momo_agent.analyzer import MoMoAnalyzer

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to momo sms json")
    ap.add_argument("--out", required=True, help="Output directory")

    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    analyzer = MoMoAnalyzer.from_json(args.input)
    df = analyzer.transactions()
    df.to_csv(outdir / "transactions.csv", index=False)

    for period in ["weekly","monthly","yearly"]:
        p = {"weekly":"week","monthly":"month","yearly":"year"}[period]
        report = analyzer.render_report(p)
        (outdir / f"report_{period}.md").write_text(report.markdown, encoding="utf-8")

    print(f"Wrote: {outdir/'transactions.csv'}")
    print(f"Wrote: {outdir/'report_weekly.md'}")
    print(f"Wrote: {outdir/'report_monthly.md'}")
    print(f"Wrote: {outdir/'report_yearly.md'}")

if __name__ == "__main__":
    main()