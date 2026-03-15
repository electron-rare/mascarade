"""Domain detector — classification rapide par mots-clés."""

from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger("mascarade.router.domain_detector")

# Type pour les domaines supportés
Domain = Literal["kicad", "spice", "freecad", "stm32", "iot", "general"]


class DomainDetector:
    """Détecteur de domaine par mots-clés."""

    def __init__(self) -> None:
        """Initialise le détecteur avec les dictionnaires de mots-clés."""
        # Dictionnaire des mots-clés par domaine
        # Ordre de priorité : spécifique > général
        self._domain_keywords: dict[str, list[str]] = {
            "kicad": [
                "kicad",
                "pcb",
                "schematic",
                "footprint",
                "netlist",
                "eeschema",
                "pcbnew",
                "gerber",
                "routing",
                "trace",
                "via",
                "pad",
                "silkscreen",
            ],
            "spice": [
                "spice",
                "ngspice",
                "ltspice",
                "pspice",
                "simulation",
                "circuit",
                "transient",
                "ac analysis",
                "dc analysis",
                "netlist",
                "subcircuit",
                "resistor",
                "capacitor",
                "inductor",
                "mosfet",
                "bjt",
                "diode",
                "opamp",
            ],
            "freecad": [
                "freecad",
                "cad",
                "3d model",
                "parametric",
                "part design",
                "sketch",
                "constraint",
                "extrude",
                "revolve",
                "fillet",
                "chamfer",
                "assembly",
                "step file",
                "stl",
            ],
            "stm32": [
                "stm32",
                "stm",
                "arm cortex",
                "cortex-m",
                "hal",
                "cubemx",
                "stm32cube",
                "uart",
                "i2c",
                "spi",
                "gpio",
                "timer",
                "adc",
                "dac",
                "pwm",
                "dma",
            ],
            "iot": [
                "iot",
                "mqtt",
                "esp32",
                "esp8266",
                "arduino",
                "raspberry pi",
                "sensor",
                "actuator",
                "embedded",
                "microcontroller",
                "wifi",
                "bluetooth",
                "zigbee",
                "lora",
                "lorawan",
            ],
        }

        # Map des domaines vers les modèles mascarade-*
        self._domain_to_model: dict[str, str] = {
            "kicad": "mascarade-kicad",
            "spice": "mascarade-spice",
            "freecad": "mascarade-freecad",
            "stm32": "mascarade-iot",  # STM32 utilise le modèle IoT
            "iot": "mascarade-iot",
        }

    def detect_domain(self, text: str) -> str:
        """
        Détecte le domaine d'un texte par matching de mots-clés.

        Args:
            text: Le texte à classifier

        Returns:
            Le nom du domaine détecté ('kicad', 'spice', 'freecad', 'stm32', 'iot')
            ou 'general' si aucun domaine n'est détecté
        """
        if not text:
            return "general"

        # Normaliser le texte : lowercase pour matching insensible à la casse
        text_lower = text.lower()

        # Compter les matches par domaine
        domain_scores: dict[str, int] = {}

        for domain, keywords in self._domain_keywords.items():
            score = 0
            for keyword in keywords:
                # Compter le nombre d'occurrences de chaque mot-clé
                if keyword.lower() in text_lower:
                    score += text_lower.count(keyword.lower())

            if score > 0:
                domain_scores[domain] = score

        # Si aucun match, retourner 'general'
        if not domain_scores:
            return "general"

        # Retourner le domaine avec le score le plus élevé
        best_domain = max(domain_scores.items(), key=lambda x: x[1])[0]

        logger.debug(
            "Domain detection: '%s' -> %s (scores: %s)",
            text[:50],
            best_domain,
            domain_scores,
        )

        return best_domain

    def get_model_for_domain(self, domain: str) -> str | None:
        """
        Retourne le nom du modèle mascarade-* correspondant au domaine.

        Args:
            domain: Le nom du domaine

        Returns:
            Le nom du modèle (ex: 'mascarade-kicad') ou None si domaine inconnu
        """
        return self._domain_to_model.get(domain)

    @property
    def supported_domains(self) -> list[str]:
        """Retourne la liste des domaines supportés."""
        return list(self._domain_keywords.keys())
