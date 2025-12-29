# MoMo Finance Agent (Rwanda)
Gain insights from your SMS!

The project features the following:

1. Parses MTN MoMo-like SMS alerts and normalizes them to transactions.
2. Generates weekly/monthly/yearly spend reports.
3. Exposes the analytics as tools an LLM can call.

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
- `out/report_monthly.md` (human-readable report)
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
- "How much did I spend last in Decomber 2025?"