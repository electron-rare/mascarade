"""Agent Log Analyst — Analyse de logs MES/ERP/machine (Factory 4.0)."""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from datetime import datetime
from typing import Any

from mascarade.agents.base import Agent
from mascarade.router.router import Strategy

# ---------------------------------------------------------------------------
# Log parsing helpers — handle syslog, JSON lines, and CSV
# ---------------------------------------------------------------------------

_SYSLOG_RE = re.compile(
    r"^(?P<timestamp>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<process>\S+?)(?:\[(?P<pid>\d+)\])?\s*:\s*"
    r"(?P<message>.*)$"
)

_ISO_TS_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
)

_SEVERITY_KEYWORDS = {
    "critical": 5,
    "crit": 5,
    "fatal": 5,
    "error": 4,
    "err": 4,
    "warning": 3,
    "warn": 3,
    "notice": 2,
    "info": 1,
    "debug": 0,
}


def _parse_line(line: str) -> dict[str, Any]:
    """Best-effort parse a single log line into structured fields."""
    line = line.strip()
    if not line:
        return {}

    # Try JSON
    if line.startswith("{"):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            pass

    # Try syslog
    m = _SYSLOG_RE.match(line)
    if m:
        return {
            "format": "syslog",
            "timestamp": m.group("timestamp"),
            "host": m.group("host"),
            "process": m.group("process"),
            "pid": m.group("pid"),
            "message": m.group("message"),
        }

    # Try ISO-timestamped line
    m = _ISO_TS_RE.match(line)
    if m:
        return {
            "format": "timestamped",
            "timestamp": m.group("timestamp"),
            "message": line[m.end() :],
        }

    return {"format": "raw", "message": line}


def _detect_severity(text: str) -> str:
    """Detect log severity from text content."""
    lower = text.lower()
    for keyword, _level in sorted(_SEVERITY_KEYWORDS.items(), key=lambda x: -x[1]):
        if keyword in lower:
            return keyword
    return "info"


def _parse_logs(raw: str) -> list[dict[str, Any]]:
    """Parse a multi-line log blob into structured entries."""
    entries = []
    for line in raw.splitlines():
        parsed = _parse_line(line)
        if parsed:
            parsed["severity"] = _detect_severity(parsed.get("message", ""))
            entries.append(parsed)
    return entries


def _parse_csv_logs(raw: str) -> list[dict[str, Any]]:
    """Parse CSV-formatted logs."""
    reader = csv.DictReader(io.StringIO(raw))
    entries = []
    for row in reader:
        row_dict = dict(row)
        msg = row_dict.get("message", row_dict.get("msg", str(row_dict)))
        row_dict["severity"] = _detect_severity(str(msg))
        entries.append(row_dict)
    return entries


def _summarize_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Produce a statistical summary of parsed log entries."""
    severity_counts: Counter = Counter()
    process_counts: Counter = Counter()
    error_messages: list[str] = []

    for e in entries:
        sev = e.get("severity", "info")
        severity_counts[sev] += 1
        process_counts[e.get("process", "unknown")] += 1
        if sev in ("error", "err", "critical", "crit", "fatal"):
            error_messages.append(e.get("message", "")[:200])

    return {
        "total_lines": len(entries),
        "severity_distribution": dict(severity_counts.most_common()),
        "top_processes": dict(process_counts.most_common(10)),
        "error_count": sum(
            severity_counts.get(s, 0) for s in ("error", "err", "critical", "crit", "fatal")
        ),
        "sample_errors": error_messages[:10],
    }


class LogAnalystAgent(Agent):
    """Agent d'analyse de logs MES, ERP et machines industrielles.

    Parse les formats syslog, JSON lines et CSV. Produit des résumés
    de poste, détecte les anomalies, et génère des rapports markdown.
    """

    def __init__(self):
        super().__init__(
            name="log-analyst",
            description=(
                "Analyse les logs MES/ERP/machine — parsing multi-format "
                "(syslog, JSON, CSV), résumés de poste, détection d'anomalies, "
                "génération de rapports markdown."
            ),
            system_prompt=(
                "Tu es un expert en analyse de logs industriels (MES, ERP, automates, SCADA). "
                "Tu sais lire et interpréter les logs syslog, JSON et CSV provenant de "
                "systèmes de production.\n\n"
                "RULES:\n"
                "- Parse the log data provided and base your analysis on actual content.\n"
                "- Identify patterns: recurring errors, frequency spikes, correlations.\n"
                "- Classify events by severity: info, warning, error, critical.\n"
                "- Generate structured markdown reports with tables when appropriate.\n"
                "- Be bilingual FR/EN — answer in the operator's language.\n"
                "- Flag security-relevant events (unauthorized access, config changes).\n"
                "- For shift summaries: focus on production-impacting events.\n"
                "- Suggest root causes for recurring errors.\n"
                "- Include timestamps and event counts in your analysis."
            ),
            preferred_provider="ollama",
            preferred_model="devstral",
            strategy=Strategy.DOMAIN,
            tools=["python", "mqtt_subscribe"],
            temperature=0.2,
            max_tokens=4096,
            category="industrial",
        )

    async def parse_logs(self, raw_logs: str, *, fmt: str = "auto", router=None) -> str:
        """Parse des logs bruts et retourne une analyse structurée."""
        if fmt == "csv" or (fmt == "auto" and "," in raw_logs.split("\n", 1)[0]):
            try:
                entries = _parse_csv_logs(raw_logs)
            except Exception:
                entries = _parse_logs(raw_logs)
        else:
            entries = _parse_logs(raw_logs)

        summary = _summarize_entries(entries)
        report = (
            f"## Log Parsing Results\n\n"
            f"- **Lines parsed:** {summary['total_lines']}\n"
            f"- **Errors/Critical:** {summary['error_count']}\n"
            f"- **Severity distribution:** {summary['severity_distribution']}\n"
            f"- **Top processes:** {summary['top_processes']}\n"
        )
        if summary["sample_errors"]:
            report += "\n### Sample Errors\n"
            for err in summary["sample_errors"]:
                report += f"- `{err}`\n"

        if router is None:
            return report

        prompt = (
            f"Voici le résultat du parsing de logs:\n\n{report}\n\n"
            f"Analyse ces résultats et fournis:\n"
            f"1. Résumé exécutif\n"
            f"2. Problèmes identifiés par ordre de gravité\n"
            f"3. Corrélations entre événements\n"
            f"4. Actions recommandées"
        )
        response = await self.run(prompt, router=router)
        return response.content

    async def summarize_shift(self, raw_logs: str, shift_info: str = "", *, router=None) -> str:
        """Résumé des logs d'un poste de travail."""
        entries = _parse_logs(raw_logs)
        summary = _summarize_entries(entries)

        stats_text = (
            f"Shift: {shift_info or 'current'}\n"
            f"Total events: {summary['total_lines']}\n"
            f"Errors: {summary['error_count']}\n"
            f"Severity: {summary['severity_distribution']}\n"
            f"Processes: {summary['top_processes']}\n"
        )
        if summary["sample_errors"]:
            stats_text += "Key errors:\n" + "\n".join(
                f"  - {e}" for e in summary["sample_errors"][:5]
            )

        if router is None:
            return stats_text

        prompt = (
            f"Génère un résumé de poste à partir de ces statistiques de logs:\n\n"
            f"{stats_text}\n\n"
            f"Format markdown:\n"
            f"# Résumé Poste — {shift_info or 'courant'}\n"
            f"## Vue d'ensemble\n"
            f"## Événements critiques\n"
            f"## Tendances\n"
            f"## Actions à transmettre"
        )
        response = await self.run(prompt, router=router)
        return response.content

    async def find_anomalies(self, raw_logs: str, *, router=None) -> str:
        """Détecte les anomalies dans les logs (pics de fréquence, patterns inhabituels)."""
        entries = _parse_logs(raw_logs)
        summary = _summarize_entries(entries)

        # Simple anomaly indicators
        anomaly_flags = []
        error_ratio = summary["error_count"] / max(summary["total_lines"], 1)
        if error_ratio > 0.1:
            anomaly_flags.append(
                f"High error ratio: {error_ratio:.1%} ({summary['error_count']}/{summary['total_lines']})"
            )

        # Check for repeated error messages
        error_msgs = [
            e.get("message", "")[:100]
            for e in entries
            if e.get("severity") in ("error", "err", "critical")
        ]
        msg_counts = Counter(error_msgs)
        for msg, count in msg_counts.most_common(5):
            if count >= 3:
                anomaly_flags.append(f"Repeated error ({count}x): {msg}")

        anomaly_report = (
            f"## Anomaly Detection\n\n"
            f"- Lines analyzed: {summary['total_lines']}\n"
            f"- Error ratio: {error_ratio:.1%}\n"
            f"- Anomalies flagged: {len(anomaly_flags)}\n"
        )
        if anomaly_flags:
            anomaly_report += "\n### Flags\n" + "\n".join(f"- {f}" for f in anomaly_flags)

        if router is None:
            return anomaly_report

        prompt = (
            f"Analyse ces anomalies détectées dans les logs:\n\n"
            f"{anomaly_report}\n\n"
            f"Fournir:\n"
            f"1. Classification de chaque anomalie\n"
            f"2. Causes probables\n"
            f"3. Impact sur la production\n"
            f"4. Actions correctives"
        )
        response = await self.run(prompt, router=router)
        return response.content

    async def generate_report(
        self,
        raw_logs: str,
        *,
        title: str = "Log Analysis Report",
        period: str = "",
        router=None,
    ) -> str:
        """Génère un rapport markdown complet d'analyse de logs."""
        entries = _parse_logs(raw_logs)
        summary = _summarize_entries(entries)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Build a structured report
        md = (
            f"# {title}\n\n"
            f"**Date:** {now}  \n"
            f"**Period:** {period or 'N/A'}  \n"
            f"**Lines analyzed:** {summary['total_lines']}  \n\n"
            f"## Severity Distribution\n\n"
            f"| Severity | Count |\n|----------|-------|\n"
        )
        for sev, count in sorted(summary["severity_distribution"].items()):
            md += f"| {sev} | {count} |\n"

        md += "\n## Top Processes\n\n" "| Process | Events |\n|---------|--------|\n"
        for proc, count in sorted(summary["top_processes"].items(), key=lambda x: -x[1])[:10]:
            md += f"| {proc} | {count} |\n"

        if summary["sample_errors"]:
            md += "\n## Critical/Error Events\n\n"
            for err in summary["sample_errors"]:
                md += f"- `{err}`\n"

        if router is None:
            return md

        prompt = (
            f"Voici un rapport de logs pré-structuré:\n\n{md}\n\n"
            f"Enrichis ce rapport avec:\n"
            f"1. Analyse exécutive (3-5 lignes)\n"
            f"2. Corrélations entre événements\n"
            f"3. Recommandations opérationnelles\n"
            f"4. Points d'attention pour le prochain poste\n\n"
            f"Conserve le format markdown et les tableaux existants."
        )
        response = await self.run(prompt, router=router)
        return response.content


if __name__ == "__main__":
    agent = LogAnalystAgent()
    print(f"Log Analyst Agent created: {agent.name}")
    print(f"Category: {agent.category}")
    print(f"Description: {agent.description}")

    # Quick self-test
    sample_logs = """Mar 25 10:00:01 plc01 opcua[1234]: INFO Connection established
Mar 25 10:00:05 plc01 opcua[1234]: WARNING High temperature on motor_3: 78.5C
Mar 25 10:01:12 plc01 scada[5678]: ERROR Communication timeout with sensor_12
Mar 25 10:01:15 plc01 scada[5678]: ERROR Communication timeout with sensor_12
Mar 25 10:01:18 plc01 scada[5678]: CRITICAL Emergency stop triggered on line_2
Mar 25 10:02:00 plc01 mes[9012]: INFO Shift report generated"""
    parsed = _parse_logs(sample_logs)
    summary = _summarize_entries(parsed)
    print(f"\nParsed {summary['total_lines']} lines, {summary['error_count']} errors")
    print(f"Severity: {summary['severity_distribution']}")
