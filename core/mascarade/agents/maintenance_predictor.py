"""Agent Maintenance Predictor — Maintenance prédictive par analyse statistique (Factory 4.0)."""

from __future__ import annotations

import statistics
from typing import Any

from mascarade.agents.base import Agent
from mascarade.router.router import Strategy


def _moving_average(values: list[float], window: int = 10) -> list[float]:
    """Compute simple moving average over a sliding window."""
    if len(values) < window:
        return values[:]
    return [statistics.mean(values[i : i + window]) for i in range(len(values) - window + 1)]


def _detect_anomalies(
    values: list[float],
    *,
    sigma: float = 3.0,
) -> list[dict[str, Any]]:
    """Flag values exceeding mean +/- sigma * stddev."""
    if len(values) < 2:
        return []
    mean = statistics.mean(values)
    std = statistics.stdev(values)
    if std == 0:
        return []
    anomalies = []
    for idx, v in enumerate(values):
        z = abs(v - mean) / std
        if z > sigma:
            anomalies.append({"index": idx, "value": v, "z_score": round(z, 2)})
    return anomalies


def _trend_slope(values: list[float]) -> float:
    """Linear regression slope (least-squares) — positive = increasing."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = statistics.mean(values)
    numer = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denom = sum((i - x_mean) ** 2 for i in range(n))
    return numer / denom if denom else 0.0


def _risk_score(
    values: list[float],
    *,
    warning_threshold: float,
    critical_threshold: float,
) -> dict[str, Any]:
    """Compute a 0-100 risk score based on current value, trend, and thresholds."""
    if not values:
        return {"score": 0, "level": "unknown", "detail": "no data"}
    current = values[-1]
    slope = _trend_slope(values[-20:]) if len(values) >= 5 else 0.0

    # Base score: how close we are to critical
    span = critical_threshold - warning_threshold
    if span <= 0:
        base = 50.0
    elif current <= warning_threshold:
        base = max(0.0, (current / warning_threshold) * 40) if warning_threshold else 0.0
    elif current <= critical_threshold:
        base = 40 + ((current - warning_threshold) / span) * 40
    else:
        base = 80 + min(20.0, (current - critical_threshold) / (span or 1) * 20)

    # Trend adjustment: rising trend adds up to 15 points
    trend_adj = min(15.0, max(-10.0, slope * 10))
    score = max(0.0, min(100.0, base + trend_adj))

    if score >= 80:
        level = "critical"
    elif score >= 50:
        level = "warning"
    elif score >= 25:
        level = "monitor"
    else:
        level = "ok"

    return {
        "score": round(score, 1),
        "level": level,
        "current_value": current,
        "trend_slope": round(slope, 4),
        "detail": f"value={current}, slope={slope:.4f}, base={base:.1f}",
    }


class MaintenancePredictorAgent(Agent):
    """Agent d'analyse prédictive pour la maintenance industrielle.

    Combine des méthodes statistiques simples (moyenne mobile, écart-type,
    régression linéaire, seuils) avec le raisonnement LLM pour interpréter
    les tendances capteurs et recommander des actions de maintenance.
    Pas de dépendance ML lourde — fonctionne avec Ollama sur Tower/KXKM.
    """

    def __init__(self):
        super().__init__(
            name="maintenance-predictor",
            description=(
                "Agent de maintenance prédictive — analyse les séries temporelles "
                "capteurs (vibration, température, courant) pour détecter les anomalies, "
                "prédire les pannes et planifier la maintenance. Méthodes statistiques légères."
            ),
            system_prompt=(
                "Tu es un expert en maintenance prédictive industrielle. "
                "Tu analyses les données capteurs (vibration, température, courant, pression) "
                "pour détecter les dérives, anomalies et prédire les pannes.\n\n"
                "RULES:\n"
                "- Base your analysis on the statistical results provided (risk scores, "
                "anomalies, trends) — do NOT invent sensor data.\n"
                "- Express risk as a score 0-100 with levels: ok / monitor / warning / critical.\n"
                "- Always recommend concrete maintenance actions with priority and timeline.\n"
                "- Reference standard predictive methods: vibration analysis (ISO 10816), "
                "thermal trending, current signature analysis.\n"
                "- Be bilingual FR/EN — answer in the operator's language.\n"
                "- For critical risks (score >= 80): recommend immediate intervention.\n"
                "- For warning (50-79): schedule maintenance within the week.\n"
                "- For monitor (25-49): add to next planned maintenance window.\n"
                "- Include MTBF/MTTR estimates when data allows."
            ),
            preferred_provider="ollama",
            preferred_model="qwen3",
            strategy=Strategy.DOMAIN,
            tools=["opcua_read", "mqtt_subscribe", "python"],
            temperature=0.2,
            max_tokens=4096,
            category="industrial",
        )

    async def analyze_trend(
        self,
        sensor_name: str,
        values: list[float],
        *,
        warning_threshold: float = 70.0,
        critical_threshold: float = 90.0,
        router=None,
    ) -> str:
        """Analyse la tendance d'un capteur et retourne une interprétation."""
        ma = _moving_average(values, window=min(10, len(values)))
        slope = _trend_slope(values)
        risk = _risk_score(
            values,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
        )

        stats_summary = (
            f"Sensor: {sensor_name}\n"
            f"Points: {len(values)}\n"
            f"Current: {values[-1] if values else 'N/A'}\n"
            f"Mean: {statistics.mean(values):.2f}\n"
            f"Std dev: {statistics.stdev(values):.2f}\n"
            f"Trend slope: {slope:.4f} ({'rising' if slope > 0 else 'falling' if slope < 0 else 'stable'})\n"
            f"Moving average (last 5): {[round(v, 2) for v in ma[-5:]]}\n"
            f"Risk score: {risk['score']}/100 ({risk['level']})\n"
            f"Thresholds: warning={warning_threshold}, critical={critical_threshold}"
        )

        if router is None:
            return stats_summary

        prompt = (
            f"Analyse cette tendance capteur et donne tes recommandations:\n\n"
            f"{stats_summary}\n\n"
            f"Fournir:\n"
            f"1. Interprétation de la tendance\n"
            f"2. Risque de panne estimé\n"
            f"3. Actions recommandées avec priorité\n"
            f"4. Délai d'intervention suggéré"
        )
        response = await self.run(prompt, router=router)
        return response.content

    async def predict_failure(
        self,
        machine_id: str,
        sensor_data: dict[str, list[float]],
        *,
        thresholds: dict[str, tuple[float, float]] | None = None,
        router=None,
    ) -> str:
        """Prédit les pannes à partir de données multi-capteurs."""
        default_thresholds: dict[str, tuple[float, float]] = {
            "vibration_mm_s": (4.5, 7.1),  # ISO 10816 class I
            "temperature_c": (70.0, 90.0),
            "current_a": (0.0, 0.0),  # needs per-machine config
            "pressure_bar": (0.0, 0.0),
        }
        thresholds = thresholds or {}

        results = []
        for sensor, values in sensor_data.items():
            if len(values) < 2:
                results.append(f"{sensor}: insufficient data ({len(values)} points)")
                continue
            warn, crit = thresholds.get(sensor, default_thresholds.get(sensor, (70.0, 90.0)))
            risk = _risk_score(values, warning_threshold=warn, critical_threshold=crit)
            anomalies = _detect_anomalies(values)
            results.append(
                f"{sensor}: risk={risk['score']}/100 ({risk['level']}), "
                f"current={risk['current_value']}, trend={risk['trend_slope']}, "
                f"anomalies={len(anomalies)}"
            )

        analysis = (
            f"Machine: {machine_id}\n"
            f"Sensors analyzed: {len(sensor_data)}\n\n" + "\n".join(results)
        )

        if router is None:
            return analysis

        prompt = (
            f"Analyse de prédiction de panne pour la machine '{machine_id}':\n\n"
            f"{analysis}\n\n"
            f"Fournir:\n"
            f"1. Évaluation globale du risque machine\n"
            f"2. Capteurs les plus critiques\n"
            f"3. Mode de défaillance probable\n"
            f"4. Temps estimé avant panne (si tendance continue)\n"
            f"5. Plan d'action maintenance (immédiat / planifié / surveillance)"
        )
        response = await self.run(prompt, router=router)
        return response.content

    async def maintenance_schedule(
        self,
        machines: dict[str, dict[str, list[float]]],
        *,
        router=None,
    ) -> str:
        """Planifie la maintenance en fonction des scores de risque multi-machines."""
        summaries = []
        for machine_id, sensors in machines.items():
            max_risk = 0.0
            critical_sensors = []
            for sensor, values in sensors.items():
                if len(values) < 2:
                    continue
                risk = _risk_score(values, warning_threshold=70.0, critical_threshold=90.0)
                if risk["score"] > max_risk:
                    max_risk = risk["score"]
                if risk["level"] in ("warning", "critical"):
                    critical_sensors.append(f"{sensor}({risk['score']})")
            summaries.append(
                f"- {machine_id}: max_risk={max_risk:.0f}/100, "
                f"flags=[{', '.join(critical_sensors) or 'none'}]"
            )

        schedule_data = "Résumé multi-machines:\n" + "\n".join(summaries)

        if router is None:
            return schedule_data

        prompt = (
            f"Planifie la maintenance préventive à partir de ces données:\n\n"
            f"{schedule_data}\n\n"
            f"Produis un planning:\n"
            f"1. Interventions urgentes (cette semaine)\n"
            f"2. Maintenance planifiée (prochain arrêt)\n"
            f"3. Surveillance renforcée\n"
            f"4. Pièces de rechange à commander\n"
            f"5. Estimation des durées d'intervention"
        )
        response = await self.run(prompt, router=router)
        return response.content

    async def anomaly_detect(
        self,
        sensor_name: str,
        values: list[float],
        *,
        sigma: float = 3.0,
        router=None,
    ) -> str:
        """Détecte les anomalies dans une série temporelle capteur."""
        anomalies = _detect_anomalies(values, sigma=sigma)
        mean = statistics.mean(values) if values else 0.0
        std = statistics.stdev(values) if len(values) >= 2 else 0.0

        report = (
            f"Sensor: {sensor_name}\n"
            f"Points: {len(values)}\n"
            f"Mean: {mean:.2f}, Std dev: {std:.2f}\n"
            f"Sigma threshold: {sigma}\n"
            f"Anomalies detected: {len(anomalies)}\n"
        )
        if anomalies:
            report += "\nAnomalies:\n"
            for a in anomalies[:20]:  # cap display
                report += f"  - index={a['index']}, value={a['value']}, z={a['z_score']}\n"

        if router is None:
            return report

        prompt = (
            f"Analyse ces anomalies capteur détectées:\n\n"
            f"{report}\n\n"
            f"Fournir:\n"
            f"1. Classification des anomalies (ponctuelle, dérive, changement de régime)\n"
            f"2. Causes probables\n"
            f"3. Impact sur la machine\n"
            f"4. Actions recommandées"
        )
        response = await self.run(prompt, router=router)
        return response.content


if __name__ == "__main__":
    agent = MaintenancePredictorAgent()
    print(f"Maintenance Predictor Agent created: {agent.name}")
    print(f"Category: {agent.category}")
    print(f"Description: {agent.description}")

    # Quick self-test of statistical helpers
    test_data = [10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 80.0, 13.5, 14.0]
    print(f"\nTest anomaly detection: {_detect_anomalies(test_data)}")
    print(f"Test trend slope: {_trend_slope(test_data):.4f}")
    print(f"Test risk score: {_risk_score(test_data, warning_threshold=50, critical_threshold=80)}")
