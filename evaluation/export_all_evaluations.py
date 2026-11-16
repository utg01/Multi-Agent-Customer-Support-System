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

WORK_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = WORK_DIR / "Langsmith_evaluation.xlsx"
ENV_FILE = WORK_DIR / ".env" if (WORK_DIR / ".env").exists() else WORK_DIR.parent / ".env"

load_dotenv(ENV_FILE)

# Configurations for the projects to export
PROJECT_CONFIGS = [
    {
        "project_name": "Routing-openai-gpt4.1mini-eval-reasoning low",
        "sheet_name": "gpt4.1mini-reasoning-low",
        "exclude_errors": True,
        "display_name": "GPT-4.1 Mini (Low Reasoning)",
    },
    {
        "project_name": "gpt oss 20b and 120b",
        "sheet_name": "gpt oss 20b and 120b",
        "exclude_errors": False,
        "display_name": "GPT OSS (20B + 120B)",
    },
    {
        "project_name": "gpt oss 120b",
        "sheet_name": "gpt oss 120b",
        "exclude_errors": False,
        "display_name": "GPT OSS (120B)",
    },
]


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


def process_project(client: Client, config: dict[str, Any], wb: openpyxl.Workbook) -> dict[str, Any]:
    project_name = config["project_name"]
    sheet_name = config["sheet_name"]
    exclude_errors = config["exclude_errors"]
    display_name = config["display_name"]

    print(f"\nFetching traces for project {project_name!r}...")
    all_runs = list(client.list_runs(project_name=project_name, is_root=True))
    total_raw_runs = len(all_runs)

    if exclude_errors:
        runs = [r for r in all_runs if r.error is None]
        excluded_count = total_raw_runs - len(runs)
        print(f"Loaded {total_raw_runs} total runs. Excluded {excluded_count} failed runs. Evaluated: {len(runs)} valid runs.")
    else:
        runs = all_runs
        excluded_count = 0
        print(f"Loaded {len(runs)} valid runs.")

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
        "display_name": display_name,
        "project_name": project_name,
        "sheet_name": sheet_name,
        "total_traces": total_traces,
        "excluded_failed_traces": excluded_count,
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

    # If sheet already exists, replace it
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]

    ws = wb.create_sheet(title=sheet_name)

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
    summary_title = f"Evaluation Summary Metrics ({display_name})"
    summary_title_cell = ws.cell(row=summary_start_row, column=1, value=summary_title)
    summary_title_cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    summary_title_cell.fill = summary_header_fill

    summary_val_header = ws.cell(row=summary_start_row, column=2, value="Value")
    summary_val_header.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    summary_val_header.fill = summary_header_fill

    summary_rows = [
        ("Total Traces (Evaluated)", total_traces, "#,##0"),
        ("Excluded Failed Traces", excluded_count, "#,##0"),
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

    # Column widths
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

    print(f"Created sheet {sheet_name!r} successfully.")
    return stats


def create_comparison_sheet(wb: openpyxl.Workbook, all_stats: list[dict[str, Any]]) -> None:
    comp_sheet_name = "Comparison Summary"
    if comp_sheet_name in wb.sheetnames:
        del wb[comp_sheet_name]

    ws = wb.create_sheet(title=comp_sheet_name)

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    metric_label_font = Font(name="Calibri", size=11, bold=True)
    regular_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    metrics = [
        ("Total Traces Evaluated", "total_traces", "#,##0"),
        ("Excluded Failed Traces", "excluded_failed_traces", "#,##0"),
        ("Total Cost ($)", "total_cost", "$#,##0.000000"),
        ("Total Tokens", "total_tokens", "#,##0"),
        ("Prompt Tokens", "total_prompt_tokens", "#,##0"),
        ("Completion Tokens", "total_completion_tokens", "#,##0"),
        ("P50 Latency (s)", "p50_latency", '0.00" s"'),
        ("P95 Latency (s)", "p95_latency", '0.00" s"'),
        ("P99 Latency (s)", "p99_latency", '0.00" s"'),
        ("Average Latency (s)", "mean_latency", '0.00" s"'),
        ("Min Latency (s)", "min_latency", '0.00" s"'),
        ("Max Latency (s)", "max_latency", '0.00" s"'),
    ]

    # Write Header Row
    c1 = ws.cell(row=1, column=1, value="Evaluation Metric")
    c1.font = header_font
    c1.fill = header_fill
    c1.alignment = Alignment(horizontal="center", vertical="center")

    for col_idx, stat in enumerate(all_stats, start=2):
        cell = ws.cell(row=1, column=col_idx, value=stat["display_name"])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Write Metric Rows
    for row_idx, (label, key, num_fmt) in enumerate(metrics, start=2):
        lc = ws.cell(row=row_idx, column=1, value=label)
        lc.font = metric_label_font
        lc.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
        lc.border = thin_border

        for col_idx, stat in enumerate(all_stats, start=2):
            val = stat.get(key, 0)
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = regular_font
            cell.border = thin_border
            cell.number_format = num_fmt
            cell.alignment = Alignment(horizontal="right")

    ws.column_dimensions["A"].width = 28
    for col_idx in range(2, len(all_stats) + 2):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = 24


def main():
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        raise RuntimeError("LANGCHAIN_API_KEY is not configured in .env file.")

    client = Client(api_key=api_key)

    if OUTPUT_FILE.exists():
        wb = openpyxl.load_workbook(OUTPUT_FILE)
    else:
        wb = openpyxl.Workbook()
        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])

    # Also load stats from the already created sheets '4o mini' and 'cost-testing' to include in comparison
    existing_stats = []
    if "4o mini" in wb.sheetnames:
        ws_4o = wb["4o mini"]
        existing_stats.append({
            "display_name": "GPT-4o Mini",
            "sheet_name": "4o mini",
            "total_traces": ws_4o.cell(55, 2).value,
            "excluded_failed_traces": 0,
            "total_cost": ws_4o.cell(56, 2).value,
            "total_tokens": ws_4o.cell(57, 2).value,
            "total_prompt_tokens": ws_4o.cell(58, 2).value,
            "total_completion_tokens": ws_4o.cell(59, 2).value,
            "p50_latency": ws_4o.cell(60, 2).value,
            "p95_latency": ws_4o.cell(61, 2).value,
            "p99_latency": ws_4o.cell(62, 2).value,
            "mean_latency": ws_4o.cell(63, 2).value,
            "min_latency": ws_4o.cell(64, 2).value,
            "max_latency": ws_4o.cell(65, 2).value,
        })

    if "cost-testing" in wb.sheetnames:
        ws_ct = wb["cost-testing"]
        existing_stats.append({
            "display_name": "GPT-4.1 Mini (cost-testing)",
            "sheet_name": "cost-testing",
            "total_traces": ws_ct.cell(55, 2).value,
            "excluded_failed_traces": 0,
            "total_cost": ws_ct.cell(56, 2).value,
            "total_tokens": ws_ct.cell(57, 2).value,
            "total_prompt_tokens": ws_ct.cell(58, 2).value,
            "total_completion_tokens": ws_ct.cell(59, 2).value,
            "p50_latency": ws_ct.cell(60, 2).value,
            "p95_latency": ws_ct.cell(61, 2).value,
            "p99_latency": ws_ct.cell(62, 2).value,
            "mean_latency": ws_ct.cell(63, 2).value,
            "min_latency": ws_ct.cell(64, 2).value,
            "max_latency": ws_ct.cell(65, 2).value,
        })

    new_stats = []
    for config in PROJECT_CONFIGS:
        stat = process_project(client, config, wb)
        new_stats.append(stat)

    all_comparison_stats = existing_stats + new_stats
    create_comparison_sheet(wb, all_comparison_stats)

    wb.save(OUTPUT_FILE)
    print(f"\nAll operations completed. Workbook saved to {OUTPUT_FILE.name}")
    print("Sheets currently in workbook:", wb.sheetnames)


if __name__ == "__main__":
    main()
