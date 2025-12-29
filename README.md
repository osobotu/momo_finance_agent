# MoMo Finance Agent
Gain insights from your MTN MoMo SMS history.

This project demonstrates how raw mobile money SMS alerts can be transformed into structured financial insights and queried using an LLM-powered agent.

## Features

1. Parses MTN MoMo–style SMS alerts and normalizes them into structured transactions.
2. Generates weekly, monthly, and yearly spending reports.
3. Exposes transaction analytics as deterministic tools that an LLM can call (no hallucinated totals).

The agent uses tool calling to retrieve and aggregate data, ensuring all numerical results come from verified computations.


## Quickstart
### 1. Create environment and install dependencies
```bash
conda create -n momo_agent_env python=3.12
conda activate momo_agent_env
pip install -r requirements.txt
```

### 2. Run the offline analyzer without API key
```bash
python scripts/analyze.py --input ./momo_sms_2025_synthetic.json --out ./out
```

Outputs:
- `out/transactions.csv` (normalized table)
- `out/report_monthly.md`
- `out/report_weekly.md`
- `out/report_yearly.md`

### 3. Run the agent with API key
Set:
```bash
export MISTRAL_API_KEY="...your key..."
```
Or create a `.env` file and add the following
```bash
MISTRAL_API_KEY="...your key..."
```

Then:
```bash
python scripts/agent_cli.py --input ./momo_sms_2025_synthetic.json
```

Try prompts like:
- "How much did I spend on utilities in March 2025?"
- "Show top 5 recipients I transferred money to."
- "What was my highest spending month and why?"
- "What is my net income in 2025?"
- "Give me a monthly report of my expenses."