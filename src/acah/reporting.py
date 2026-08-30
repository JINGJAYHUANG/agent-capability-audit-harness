from __future__ import annotations

import html
from typing import Any


def render_markdown(
    summary: dict[str, Any],
    case_results: list[dict[str, Any]],
    capability_matrix: dict[str, Any],
) -> str:
    lines = [
        "# Agent Capability Audit Report",
        "",
        f"**Overall result:** {'PASS' if summary['passed'] else 'FAIL'}",
        "",
        "> This report evaluates a declared capability contract, policy decisions, adapter observations, and recorded evidence. It is not a security certification or proof that an external runtime is sandboxed.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for label, key in (
        ("Cases", "case_count"),
        ("Passed cases", "passed_cases"),
        ("Actions", "action_count"),
        ("Gate accuracy", "gate_accuracy"),
        ("Evidence completeness", "evidence_completeness"),
        ("Deny leakage", "deny_leakage"),
        ("Ask bypass", "ask_bypass"),
        ("Budget violations", "budget_violations"),
        ("Capabilities evaluated", "capabilities_evaluated"),
        ("Capabilities violated", "capabilities_violated"),
    ):
        lines.append(f"| {label} | {summary[key]} |")

    lines.extend(["", "## Golden task results", ""])
    for result in case_results:
        lines.append(
            f"### {'PASS' if result['passed'] else 'FAIL'} — {result['case_id']}: {result['title']}"
        )
        lines.append("")
        if result["errors"]:
            for error in result["errors"]:
                lines.append(f"- {error}")
        else:
            lines.append("- Policy decisions, expected observations, budgets, and evidence checks passed.")
        lines.append("")
        lines.append("| Action | Capability | Base | Effective | Observation |")
        lines.append("|---|---|---|---|---|")
        observations = {
            item.get("action_id"): item.get("event_type")
            for item in result["observations"]
            if item.get("action_id")
        }
        for decision in result["decisions"]:
            lines.append(
                f"| {decision['action_id']} | {decision['capability']} | {decision['base_verdict']} | {decision['verdict']} | {observations.get(decision['action_id'], 'missing')} |"
            )
        lines.append("")

    lines.extend(["## Capability matrix", "", "| Capability | Declared | Requested | Executed | Blocked | Violations | Status |", "|---|---|---:|---:|---:|---:|---|"])
    for row in capability_matrix["capabilities"]:
        lines.append(
            f"| {row['capability']} | {row['declared_verdict']} | {row['requested']} | {row['executed']} | {row['blocked']} | {row['violations']} | {row['status']} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_html(
    summary: dict[str, Any],
    case_results: list[dict[str, Any]],
    capability_matrix: dict[str, Any],
) -> str:
    status = "PASS" if summary["passed"] else "FAIL"
    case_cards = []
    for result in case_results:
        errors = "".join(f"<li>{html.escape(error)}</li>" for error in result["errors"])
        if not errors:
            errors = "<li>Policy, observation, budget, and evidence checks passed.</li>"
        rows = []
        observations = {
            item.get("action_id"): item.get("event_type")
            for item in result["observations"]
            if item.get("action_id")
        }
        for decision in result["decisions"]:
            rows.append(
                "<tr>"
                f"<td>{html.escape(decision['action_id'])}</td>"
                f"<td>{html.escape(decision['capability'])}</td>"
                f"<td>{html.escape(decision['base_verdict'])}</td>"
                f"<td>{html.escape(decision['verdict'])}</td>"
                f"<td>{html.escape(str(observations.get(decision['action_id'], 'missing')))}</td>"
                "</tr>"
            )
        case_cards.append(
            f"<section class='card'><h2>{'PASS' if result['passed'] else 'FAIL'} — {html.escape(result['case_id'])}</h2>"
            f"<p>{html.escape(result['title'])}</p><ul>{errors}</ul>"
            "<table><thead><tr><th>Action</th><th>Capability</th><th>Base</th><th>Effective</th><th>Observation</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></section>"
        )
    matrix_rows = "".join(
        "<tr>"
        f"<td>{html.escape(row['capability'])}</td>"
        f"<td>{html.escape(row['declared_verdict'])}</td>"
        f"<td>{row['requested']}</td><td>{row['executed']}</td><td>{row['blocked']}</td>"
        f"<td>{row['violations']}</td><td>{html.escape(row['status'])}</td>"
        "</tr>"
        for row in capability_matrix["capabilities"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Capability Audit Report</title>
<style>
:root{{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#172033;background:#f3f6fa}}body{{margin:0}}main{{max-width:1120px;margin:auto;padding:32px 18px 60px}}.hero,.card{{background:white;border:1px solid #dce3ed;border-radius:14px;padding:22px;margin-bottom:18px;box-shadow:0 8px 24px rgba(20,35,60,.05)}}h1{{margin:0 0 8px}}.status{{font-weight:800;font-size:28px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:18px}}.metric{{background:#f7f9fc;border-radius:10px;padding:12px}}.metric b{{display:block;font-size:22px}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;border-bottom:1px solid #e5eaf1;padding:9px 8px;vertical-align:top}}th{{color:#526078}}ul{{padding-left:20px}}.note{{color:#5b687c}}@media(max-width:700px){{table{{display:block;overflow-x:auto;white-space:nowrap}}}}
</style></head><body><main>
<section class="hero"><h1>Agent Capability Audit Report</h1><div class="status">{status}</div><p class="note">Evidence-based capability evaluation. Not a sandbox certification.</p>
<div class="grid">
<div class="metric"><span>Cases</span><b>{summary['passed_cases']}/{summary['case_count']}</b></div>
<div class="metric"><span>Gate accuracy</span><b>{summary['gate_accuracy']:.1%}</b></div>
<div class="metric"><span>Evidence</span><b>{summary['evidence_completeness']:.1%}</b></div>
<div class="metric"><span>Deny leakage</span><b>{summary['deny_leakage']}</b></div>
<div class="metric"><span>Ask bypass</span><b>{summary['ask_bypass']}</b></div>
</div></section>
{''.join(case_cards)}
<section class="card"><h2>Capability matrix</h2><table><thead><tr><th>Capability</th><th>Declared</th><th>Requested</th><th>Executed</th><th>Blocked</th><th>Violations</th><th>Status</th></tr></thead><tbody>{matrix_rows}</tbody></table></section>
</main></body></html>"""
