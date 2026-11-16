from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langsmith import Client
import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

PROJECT_NAME = "cost testing all 4.1 mini"
TARGET_SHEET_NAME = "4o mini"
WORK_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = WORK_DIR / "Langsmith_evaluation.xlsx"
ENV_FILE = WORK_DIR / ".env" if (WORK_DIR / ".env").exists() else WORK_DIR.parent / ".env"

load_dotenv(ENV_FILE)


def _format_datetime(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _message_content(message: Any) -> str | None:
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text = " ".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ).strip()
            return text or None
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content
    return None


def _extract_input(inputs: Any) -> str | None:
    if isinstance(inputs, dict):
        messages = inputs.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                if isinstance(message, dict) and message.get("type") in (None, "human"):
                    content = _message_content(message)
                    if content:
                        return content
        if inputs.get("input") is not None:
            return str(inputs["input"])
    return str(inputs) if inputs else None


def _extract_output(outputs: Any) -> str | None:
    if not isinstance(outputs, dict):
        return str(outputs) if outputs else None

    active_agent = outputs.get("active_agent")
    if active_agent:
        return str(active_agent)

    messages = outputs.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            content = _message_content(message)
            if content:
                return content
    return None


def _extract_error(error: Any) -> str | None:
    if error is None:
        return None
    if isinstance(error, str):
        return error.strip() or None
    if isinstance(error, dict):
        meaningful_error = {
            key: value for key, value in error.items() if value not in (None, "")
        }
        return str(meaningful_error) if meaningful_error else None
    return str(error).strip() or None


def export_traces_and_stats() -> dict[str, Any]:
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        raise RuntimeError("LANGCHAIN_API_KEY is not configured in .env file.")

    client = Client(api_key=api_key)
    print(f"Loading root traces from project: {PROJECT_NAME!r}...")

    # Fetch root runs
    runs = list(client.list_runs(project_name=PROJECT_NAME, is_root=True))
    if not runs:
        raise RuntimeError(f"No root traces found for project {PROJECT_NAME!r}.")

    print(f"Loaded {len(runs)} traces successfully.")

    extracted_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    costs: list[float] = []
    total_tokens_list: list[int] = []
    prompt_tokens_list: list[int] = []
    comp_tokens_list: list[int] = []

    for run in runs:
        latency = None
        if run.start_time and run.end_time:
            latency = (run.end_time - run.start_time).total_seconds()
            latencies.append(latency)

        cost = getattr(run, "total_cost", None) or 0.0
        costs.append(cost)

        tot_tok = getattr(run, "total_tokens", None) or 0
        p_tok = getattr(run, "prompt_tokens", None) or 0
        c_tok = getattr(run, "completion_tokens", None) or 0

        total_tokens_list.append(tot_tok)
        prompt_tokens_list.append(p_tok)
        comp_tokens_list.append(c_tok)

        extracted_rows.append(
            {
                "Name": run.name,
                "Input": _extract_input(run.inputs),
                "Output": _extract_output(run.outputs),
                "Error": _extract_error(run.error),
                "Start Time": _format_datetime(run.start_time),
                "End Time": _format_datetime(run.end_time),
                "Latency (s)": round(latency, 2) if latency is not None else None,
                "Total Tokens": tot_tok,
                "Prompt Tokens": p_tok,
                "Completion Tokens": c_tok,
                "Total Cost ($)": cost,
            }
        )

    # Statistical calculations
    total_traces = len(runs)
    total_cost = sum(costs)
    total_tokens = sum(total_tokens_list)
    total_prompt_tokens = sum(prompt_tokens_list)
    total_completion_tokens = sum(comp_tokens_list)

    p50_latency = float(np.percentile(latencies, 50)) if latencies else 0.0
    p95_latency = float(np.percentile(latencies, 95)) if latencies else 0.0
    p99_latency = float(np.percentile(latencies, 99)) if latencies else 0.0
    mean_latency = float(np.mean(latencies)) if latencies else 0.0
    min_latency = float(np.min(latencies)) if latencies else 0.0
    max_latency = float(np.max(latencies)) if latencies else 0.0

    stats = {
        "total_traces": total_traces,
        "total_cost": total_cost,
        "total_tokens": total_tokens,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "p50_latency": p50_latency,
        "p95_latency": p95_latency,
        "p99_latency": p99_latency,
        "mean_latency": mean_latency,
        "min_latency": min_latency,
        "max_latency": max_latency,
    }

    # Open existing workbook or create a new one, keeping other sheets untouched
    if OUTPUT_FILE.exists():
        wb = openpyxl.load_workbook(OUTPUT_FILE)
    else:
        wb = openpyxl.Workbook()
        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])

    # If sheet already exists, replace it
    if TARGET_SHEET_NAME in wb.sheetnames:
        del wb[TARGET_SHEET_NAME]

    ws = wb.create_sheet(title=TARGET_SHEET_NAME)

    # Styles
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    summary_header_fill = PatternFill(start_color="203764", end_color="203764", fill_type="solid")
    metric_label_font = Font(name="Calibri", size=11, bold=True)
    regular_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    # Write Data Headers
    headers = list(extracted_rows[0].keys())
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Write Data Rows
    for row_idx, data_row in enumerate(extracted_rows, start=2):
        for col_idx, header in enumerate(headers, start=1):
            val = data_row[header]
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = regular_font
            cell.border = thin_border
            if header in ("Total Tokens", "Prompt Tokens", "Completion Tokens"):
                cell.number_format = "#,##0"
                cell.alignment = Alignment(horizontal="right")
            elif header == "Total Cost ($)":
                cell.number_format = "$#,##0.000000"
                cell.alignment = Alignment(horizontal="right")
            elif header == "Latency (s)":
                cell.number_format = "0.00"
                cell.alignment = Alignment(horizontal="right")
            elif header in ("Start Time", "End Time"):
                cell.alignment = Alignment(horizontal="center")

    last_data_row = len(extracted_rows) + 1

    # Write Summary Section below data table
    summary_start_row = last_data_row + 3
    summary_title_cell = ws.cell(row=summary_start_row, column=1, value="Evaluation Summary Metrics (4o mini)")
    summary_title_cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    summary_title_cell.fill = summary_header_fill

    summary_val_header = ws.cell(row=summary_start_row, column=2, value="Value")
    summary_val_header.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    summary_val_header.fill = summary_header_fill

    summary_rows = [
        ("Total Traces", total_traces, "#,##0"),
        ("Total Cost ($)", total_cost, "$#,##0.000000"),
        ("Total Tokens", total_tokens, "#,##0"),
        ("Prompt Tokens", total_prompt_tokens, "#,##0"),
        ("Completion Tokens", total_completion_tokens, "#,##0"),
        ("P50 Latency (s)", p50_latency, "0.0000"),
        ("P95 Latency (s)", p95_latency, "0.0000"),
        ("P99 Latency (s)", p99_latency, "0.0000"),
        ("Average Latency (s)", mean_latency, "0.0000"),
        ("Min Latency (s)", min_latency, "0.0000"),
        ("Max Latency (s)", max_latency, "0.0000"),
    ]

    for offset, (metric_name, metric_val, num_fmt) in enumerate(summary_rows, start=1):
        curr_row = summary_start_row + offset
        c1 = ws.cell(row=curr_row, column=1, value=metric_name)
        c1.font = metric_label_font
        c1.border = thin_border
        c1.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

        c2 = ws.cell(row=curr_row, column=2, value=metric_val)
        c2.font = regular_font
        c2.number_format = num_fmt
        c2.border = thin_border
        c2.alignment = Alignment(horizontal="right")

    # Adjust Column Widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        # Check first 55 rows for length
        for cell in col[:65]:
            if cell.row > last_data_row and cell.row < summary_start_row:
                continue
            if cell.value:
                first_line = str(cell.value).split("\n")[0]
                max_len = max(max_len, min(len(first_line), 60))
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # Specific widths for clarity
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 45
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 25
    ws.column_dimensions["E"].width = 20
    ws.column_dimensions["F"].width = 20
    ws.column_dimensions["G"].width = 14
    ws.column_dimensions["H"].width = 14
    ws.column_dimensions["I"].width = 14
    ws.column_dimensions["J"].width = 16
    ws.column_dimensions["K"].width = 16

    wb.save(OUTPUT_FILE)
    print(f"Successfully saved sheet {TARGET_SHEET_NAME!r} into {OUTPUT_FILE.name}")
    print("Sheets now present in workbook:", wb.sheetnames)

    return stats


if __name__ == "__main__":
    stats = export_traces_and_stats()
    print("\n" + "=" * 50)
    print("       LANGSMITH EVALUATION METRICS (4o mini)")
    print("=" * 50)
    print(f"  Project:             {PROJECT_NAME}")
    print(f"  Target Sheet:        {TARGET_SHEET_NAME}")
    print(f"  Total Traces:        {stats['total_traces']}")
    print(f"  Total Cost ($):      ${stats['total_cost']:.6f}")
    print(f"  Total Tokens:        {stats['total_tokens']:,}")
    print(f"  Prompt Tokens:       {stats['total_prompt_tokens']:,}")
    print(f"  Completion Tokens:   {stats['total_completion_tokens']:,}")
    print(f"  P50 Latency:         {stats['p50_latency']:.4f}s")
    print(f"  P95 Latency:         {stats['p95_latency']:.4f}s")
    print(f"  P99 Latency:         {stats['p99_latency']:.4f}s")
    print(f"  Average Latency:     {stats['mean_latency']:.4f}s")
    print(f"  Min Latency:         {stats['min_latency']:.4f}s")
    print(f"  Max Latency:         {stats['max_latency']:.4f}s")
    print("=" * 50)
