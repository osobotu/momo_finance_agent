import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import os
import logging
from datetime import datetime
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

from mistralai import Mistral

from momo_agent.analyzer import MoMoAnalyzer
from momo_agent.tools import make_tools

from dotenv import load_dotenv

load_dotenv()

# logging 
def _new_session_logger(log_dir: str = "logs") -> logging.Logger:
    """
    Create a fresh logger per run (new chat history).
    Logs to logs/chat_YYYYMMDD_HHMMSS.log
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(log_dir) / "chat.log"

    logger = logging.getLogger(f"momo_agent_chat_{session_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)

    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    sh.setLevel(logging.WARNING)

    logger.addHandler(fh)
    logger.addHandler(sh)

    logger.info("=== NEW CHAT SESSION STARTED ===")
    logger.info(f"log_file={log_path}")
    return logger


def _log_tool_calls(logger: logging.Logger, tool_calls: Any) -> None:
    try:
        logger.info(f"tool_calls={tool_calls}")
    except Exception:
        logger.info("tool_calls=<unserializable>")


def _log_json(logger: logging.Logger, label: str, payload: Any) -> None:
    try:
        logger.info(f"{label}={json.dumps(payload, ensure_ascii=False, default=str)}")
    except Exception:
        logger.info(f"{label}=<unserializable>")


console = Console()

def _allowed_args_from_schema(tools_schema: List[Dict[str, Any]]) -> Dict[str, set]:
    """
    Build a map: tool_name -> allowed argument keys, from the JSON schema.
    """
    allowed = {}
    for t in tools_schema:
        fn = t.get("function", {})
        name = fn.get("name")
        props = (fn.get("parameters", {}) or {}).get("properties", {}) or {}
        allowed[name] = set(props.keys())
    return allowed

def _safe_tool_call(
    tools_py: Dict[str, Any],
    allowed_args: Dict[str, set],
    fn: str,
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a tool safely:
    - filters out unexpected args
    - catches any exceptions and returns structured error
    """
    if fn not in tools_py:
        return {"ok": False, "error": f"Unknown tool: {fn}"}

    allowed = allowed_args.get(fn, set())
    safe_args = {k: v for k, v in (args or {}).items() if k in allowed}

    try:
        result = tools_py[fn](**safe_args)
        return {"ok": True, "data": result, "filtered_args": safe_args}
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "filtered_args": safe_args,
        }

def _tool_schemas():
    return [
        {
            "type": "function",
            "function": {
                "name": "get_overall_summary",
                "description": "Get overall totals: income, expense, fees, net, tx_count.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_period_summary",
                "description": "Get summary for a period: week, month, or year. Optionally filter by date range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "period": {"type": "string", "enum": ["week", "month", "year"]},
                        "start": {"type": "string", "description": "YYYY-MM-DD or ISO datetime"},
                        "end": {"type": "string", "description": "YYYY-MM-DD or ISO datetime"},
                    },
                    "required": ["period"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_top_spend_counterparties",
                "description": "Top counterparties by amount spent (direction=out).",
                "parameters": {
                    "type": "object",
                    "properties": {"n": {"type": "integer", "minimum": 1, "maximum": 50}},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_category_breakdown",
                "description": "Expense totals grouped by category.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_transactions",
                "description": "Search transactions by filters (text, date range, direction, category).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "start": {"type": "string", "description": "YYYY-MM-DD or ISO datetime"},
                        "end": {"type": "string", "description": "YYYY-MM-DD or ISO datetime"},
                        "direction": {"type": "string", "enum": ["in", "out", "unknown"]},
                        "category": {"type": "string", "enum": ["transfer", "merchant", "utilities", "cash", "other"]},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                    "required": [],
                },
            },
        },
    ]

SYSTEM = (
    "You are MoMo Finance Agent. Use tools for any calculation or totals. "
    "Never invent numbers. If a question cannot be answered from tools, say so "
    "and suggest the closest query (e.g., ask for a date range). "
    "Keep answers short and actionable."
    "If a tool returns ok=false, explain the issue briefly and try another tool call or ask a clarifying question."
)

INTRO_MESSAGE = (
    "Hi! I'm your MoMo Finance Agent.\n\n"
    "I can help you:\n"
    "• Summarize your income, spending, fees, and net balance\n"
    "• Break down expenses by week, month, or year\n"
    "• Show top people or businesses you send money to\n"
    "• Analyze spending by category (utilities, merchants, transfers)\n"
    "• Search and filter transactions by date, name, or keyword\n\n"
    "Ask a question like:\n"
    "• “How much did I spend on MTN Cash Power in 2025?”\n"
    "• “What was my highest spending month?”\n"
    "• “Who do I send money to most?”\n\n"
    "Type 'exit' to quit."
)

def run_agent(analyzer: MoMoAnalyzer, model: str):
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise SystemExit("Missing MISTRAL_API_KEY env var.")
    
    client = Mistral(api_key=api_key)
    tools_py = make_tools(analyzer)
    tools_schema = _tool_schemas()
    allowed_args = _allowed_args_from_schema(tools_schema)

    logger = _new_session_logger()
    logger.info(f"model={model}")
    
 

    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM}]
    console.print(Panel(INTRO_MESSAGE, title="Agent"))
    messages.append({"role": "assistant","content": INTRO_MESSAGE})
    logger.info("assistant_intro=" + INTRO_MESSAGE.replace("\n", "\\n"))

    while True:
        user = console.input("\n[bold]You:[/bold] ").strip()
        if user.lower() in {"exit", "quit"}:
            logger.info("=== CHAT SESSION ENDED ===")
            break

        logger.info("user=" + user.replace("\n", "\\n"))
        messages.append({"role": "user", "content": user})

        try:
            resp = client.chat.complete(
                model=model,
                messages=messages,
                tools=tools_schema,
            )
        except Exception:
            logger.exception("first_model_call_failed")
            err = "Sorry — I ran into an API error. Please try again."
            console.print(Panel(err, title="Agent"))
            messages.append({"role": "assistant", "content": err})
            logger.info("assistant_final=" + err.replace("\n", "\\n"))
            continue

        msg = resp.choices[0].message
        logger.info("assistant_raw=" + (msg.content or "").replace("\n", "\\n"))
        assistant_entry: Dict[str, Any] = {"role": "assistant", "content": msg.content or ""}

        if getattr(msg, "tool_calls", None):
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in msg.tool_calls
            ]

        messages.append(assistant_entry)

        if not getattr(msg, "tool_calls", None):
            final = msg.content or "I’m not sure how to help with that—can you rephrase?"
            console.print(Panel(final, title="Agent"))
            continue

        console.print(Panel(Pretty(msg.tool_calls), title="Tool calls"))

        for tc in msg.tool_calls:
            fn = tc.function.name

            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception as e:
                tool_out = {"ok": False, "error": f"Bad tool arguments JSON: {e}"}
            else:
                tool_out = _safe_tool_call(tools_py, allowed_args, fn, args)
            _log_json(logger, f"tool_result[{fn}]", tool_out)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": fn,
                    "content": json.dumps(tool_out, ensure_ascii=False, default=str),
                }
            )

        try:
            resp2 = client.chat.complete(
                model=model,
                messages=messages,
                tools=tools_schema,
            )
            final = resp2.choices[0].message.content or "Done."
        except Exception:
            logger.exception("second_model_call_failed")
            final = "Sorry — I ran into an API error while forming the final answer."

        console.print(Panel(final, title="Agent"))
        logger.info("assistant_final=" + (final or "").replace("\n", "\\n"))
        messages.append({"role": "assistant", "content": final})



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to momo sms json")
    ap.add_argument("--model", default="mistral-small-latest", help="Mistral model name")
    args = ap.parse_args()

    analyzer = MoMoAnalyzer.from_json(args.input)
    run_agent(analyzer, model=args.model)

if __name__ == "__main__":
    main()