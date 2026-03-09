#!/usr/bin/env python3
"""Dataset refresh helpers for fine-tuning workflows.

Refresh policy:
- prefer the full `mascarade-datasets` repo when present
- otherwise rebuild the canonical JSONL from the active `finetune/datasets/build_*` script
- always emit an associated web-research brief unless explicitly disabled

Legacy note:
- old builders under `finetune/build_*` are intentionally ignored by this workflow
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dataset_bootstrap import seed_builder_for_domain
from dataset_quality import DatasetQualityError, enforce_dataset_quality, summarize_quality_report
from sharegpt_utils import (
    dedupe_rows_with_stats,
    ensure_row_ids_with_stats,
    load_jsonl,
    validate_rows,
    write_jsonl,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DATASETS_DIR = SCRIPT_DIR / "datasets"
DEFAULT_FULL_DATASETS_ROOT = SCRIPT_DIR.parent.parent / "mascarade-datasets"
DEFAULT_RESEARCH_DIR = SCRIPT_DIR / "research"
RESEARCH_SOURCES_DIR = SCRIPT_DIR / "research_sources" / "domains"
DEFAULT_RESEARCH_PROBES_DIR = SCRIPT_DIR / "research_probes"
RESEARCH_PROBE_MAX_AGE_SECONDS = 7 * 24 * 3600
SUPPORTED_DOMAINS = [
    "stm32",
    "spice",
    "iot",
    "power",
    "dsp",
    "emc",
    "kicad",
    "embedded",
    "platformio",
    "freecad",
    "components",
]
LEGACY_IGNORED_PATHS = [
    "finetune/build_components_dataset.py",
    "finetune/build_freecad_dataset.py",
]
URL_ENTRY_KEYS = (
    "authoritative_urls",
    "github_repos",
    "software_sources",
    "forum_urls",
    "datasheet_roots",
)

EMBEDDED_FORUM_URLS = [
    ("ST Community", "https://community.st.com/"),
    ("PlatformIO Community", "https://community.platformio.org/"),
    ("ChibiOS Forum", "https://forum.chibios.org/"),
    ("FreeRTOS Forums", "https://forums.freertos.org/"),
    ("ARM Community Forums", "https://community.arm.com/support-forums/"),
    ("Arduino Forum", "https://forum.arduino.cc/"),
    ("EmbeddedRelated Forum", "https://www.embeddedrelated.com/forum.php"),
    ("Electronics StackExchange STM32", "https://electronics.stackexchange.com/questions/tagged/stm32"),
    ("Electronics StackExchange Embedded", "https://electronics.stackexchange.com/questions/tagged/embedded"),
    ("All About Circuits Embedded Systems", "https://forum.allaboutcircuits.com/forums/embedded-systems-and-microcontrollers.13/"),
]

ELECTRONICS_SIM_FORUM_URLS = [
    ("ngspice Discussions", "https://sourceforge.net/p/ngspice/discussion/"),
    ("LTspice Groups", "https://groups.io/g/LTspice"),
    ("Cadence Community", "https://community.cadence.com/"),
    ("Analog Devices EngineerZone", "https://ez.analog.com/"),
    ("TI E2E", "https://e2e.ti.com/"),
    ("All About Circuits Forum", "https://forum.allaboutcircuits.com/"),
    ("EEVblog Forum", "https://www.eevblog.com/forum/"),
    ("Electronics StackExchange SPICE", "https://electronics.stackexchange.com/questions/tagged/spice"),
    ("Electronics StackExchange LTspice", "https://electronics.stackexchange.com/questions/tagged/ltspice"),
    ("PSMA Technical Forums", "https://psma.com/technical-forums/"),
]

ELECTRONICS_FORUM_URLS = [
    ("Electronics StackExchange", "https://electronics.stackexchange.com/"),
    ("All About Circuits Forum", "https://forum.allaboutcircuits.com/"),
    ("EEVblog Forum", "https://www.eevblog.com/forum/"),
    ("DigiKey TechForum", "https://forum.digikey.com/"),
    ("element14 Community", "https://community.element14.com/"),
    ("TI E2E", "https://e2e.ti.com/"),
    ("Analog Devices EngineerZone", "https://ez.analog.com/"),
    ("Infineon Community", "https://community.infineon.com/"),
    ("NXP Community", "https://community.nxp.com/"),
    ("Arduino Forum", "https://forum.arduino.cc/"),
]

DSP_FORUM_URLS = [
    ("DSP StackExchange", "https://dsp.stackexchange.com/"),
    ("DSPRelated Forums", "https://www.dsprelated.com/forums/"),
    ("MathWorks MATLAB Answers", "https://www.mathworks.com/matlabcentral/answers/"),
    ("GNU Radio Discuss", "https://forum.gnuradio.org/"),
    ("ARM Community Forums", "https://community.arm.com/support-forums/"),
    ("EmbeddedRelated Forum", "https://www.embeddedrelated.com/forum.php"),
    ("NI Forums", "https://forums.ni.com/"),
    ("Scientific Python Discourse", "https://discuss.scientific-python.org/"),
    ("Julia Discourse Signal Processing", "https://discourse.julialang.org/tag/signal-processing"),
    ("EEVblog Forum", "https://www.eevblog.com/forum/"),
]

EDA_FORUM_URLS = [
    ("KiCad.info Forums", "https://forum.kicad.info/"),
    ("KiCad Community Forums", "https://www.kicad.org/community/forums/"),
    ("EEVblog Forum", "https://www.eevblog.com/forum/"),
    ("Electronics StackExchange PCB Design", "https://electronics.stackexchange.com/questions/tagged/pcb-design"),
    ("EDAboard", "https://www.edaboard.com/"),
    ("EasyEDA Forum", "https://easyeda.com/forum/"),
    ("Altium Forum", "https://forum.live.altium.com/"),
    ("Arduino Forum", "https://forum.arduino.cc/"),
    ("All About Circuits Forum", "https://forum.allaboutcircuits.com/"),
    ("element14 Community", "https://community.element14.com/"),
]

CAD_FORUM_URLS = [
    ("FreeCAD Forum", "https://forum.freecad.org/"),
    ("CadQuery Community", "https://community.cadquery.org/"),
    ("OpenSCAD Lists", "https://lists.openscad.org/"),
    ("Autodesk Forums", "https://forums.autodesk.com/"),
    ("Onshape Forum", "https://forum.onshape.com/"),
    ("GrabCAD Questions", "https://grabcad.com/questions"),
    ("3D Printing StackExchange", "https://3dprinting.stackexchange.com/"),
    ("LibreCAD Forum", "https://forum.librecad.org/"),
    ("OpenBuilds Forum", "https://openbuilds.com/forums/"),
    ("Maker Forums", "https://forum.makerforums.info/"),
]


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _ensure_research_probe(domain: str, probes_dir: Path | None = None) -> dict | None:
    if _env_flag("MASCARADE_SKIP_LIVE_RESEARCH_PROBE", False):
        return None
    probe_dir = probes_dir or DEFAULT_RESEARCH_PROBES_DIR
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe_path = probe_dir / f"{domain}.json"
    needs_refresh = True
    if probe_path.exists():
        age_seconds = time.time() - probe_path.stat().st_mtime
        if age_seconds <= RESEARCH_PROBE_MAX_AGE_SECONDS:
            needs_refresh = False
    if needs_refresh:
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "probe_research_sources.py"),
                domain,
                "--sources-dir",
                str(RESEARCH_SOURCES_DIR),
                "--output-dir",
                str(probe_dir),
                "--json",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if not probe_path.exists():
        return None
    return json.loads(probe_path.read_text(encoding="utf-8"))

DOMAIN_RESEARCH = {
    "stm32": {
        "topic": "STM32 / Cortex-M firmware",
        "minimum_web_roots": 8,
        "forum_urls": EMBEDDED_FORUM_URLS,
        "authoritative_urls": [
            ("ST STM32Cube docs", "https://dev.st.com/stm32cube-docs/"),
            ("ST Community", "https://community.st.com/"),
        ],
        "github_repos": [
            ("STMicroelectronics org", "https://github.com/STMicroelectronics"),
            ("STM32CubeF4", "https://github.com/STMicroelectronics/STM32CubeF4"),
            ("STM32CubeH7", "https://github.com/STMicroelectronics/STM32CubeH7"),
            ("STM32CubeG4", "https://github.com/STMicroelectronics/STM32CubeG4"),
        ],
        "software_sources": [
            ("STM32Cube firmware hub", "https://github.com/STMicroelectronics"),
            ("STM32Cube docs", "https://dev.st.com/stm32cube-docs/"),
        ],
        "datasheet_roots": [
            (
                "STM32 mainstream MCU documentation hub",
                "https://www.st.com/en/microcontrollers-microprocessors/stm32-mainstream-mcus/documentation.html",
            ),
            (
                "STM32 family documentation portal",
                "https://www.st.com/en/microcontrollers-microprocessors.html",
            ),
        ],
        "hf_sources": ["MuratKomurcu/stm32-hal-dataset"],
        "queries": [
            "site:dev.st.com stm32 dma uart application note",
            "site:community.st.com stm32 freertos low power",
            "site:huggingface.co/datasets stm32 hal dataset",
        ],
        "trusted_domains": ["dev.st.com", "community.st.com", "huggingface.co"],
    },
    "spice": {
        "topic": "SPICE / circuit simulation",
        "minimum_web_roots": 8,
        "forum_urls": ELECTRONICS_SIM_FORUM_URLS,
        "authoritative_urls": [
            ("ngspice documentation", "https://ngspice.sourceforge.io/docs.html"),
            (
                "LTspice overview",
                "https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html",
            ),
        ],
        "github_repos": [
            ("ngspice", "https://github.com/ngspice/ngspice"),
        ],
        "software_sources": [
            ("ngspice upstream", "https://ngspice.sourceforge.io/"),
            (
                "LTspice download and models",
                "https://www.analog.com/en/resources/simulation-models/spice-models.html",
            ),
        ],
        "datasheet_roots": [
            (
                "Analog Devices LTspice macromodels",
                "https://www.analog.com/en/resources/simulation-models/spice-models.html",
            ),
        ],
        "hf_sources": ["STEM-AI-mtl/Electrical-engineering"],
        "queries": [
            "site:ngspice.sourceforge.io ngspice convergence transient noise",
            "site:analog.com ltspice switch-mode power simulation",
            "site:huggingface.co/datasets electrical engineering spice dataset",
        ],
        "trusted_domains": ["ngspice.sourceforge.io", "analog.com", "huggingface.co"],
    },
    "iot": {
        "topic": "IoT / ESP-IDF / Home Assistant",
        "minimum_web_roots": 8,
        "forum_urls": EMBEDDED_FORUM_URLS,
        "authoritative_urls": [
            (
                "ESP-IDF programming guide",
                "https://docs.espressif.com/projects/esp-idf/en/stable/esp32/",
            ),
            ("Home Assistant developer docs", "https://developers.home-assistant.io/"),
        ],
        "github_repos": [
            ("esp-idf", "https://github.com/espressif/esp-idf"),
            ("espressif org", "https://github.com/espressif"),
            ("home-assistant core", "https://github.com/home-assistant/core"),
        ],
        "software_sources": [
            ("ESP-IDF product page", "https://www.espressif.com/en/products/sdks/esp-idf"),
            ("Home Assistant developer portal", "https://developers.home-assistant.io/"),
        ],
        "datasheet_roots": [
            (
                "ESP32 hardware reference",
                "https://docs.espressif.com/projects/esp-idf/en/stable/esp32/hw-reference/index.html",
            ),
        ],
        "hf_sources": [
            "gouthamsk/esp_idf_code",
            "acon96/Home-Assistant-Requests",
            "gavmac00/arduino-docs",
            "bshada/arduino.stackexchange.com",
        ],
        "queries": [
            "site:docs.espressif.com esp-idf mqtt ota deep sleep",
            "site:developers.home-assistant.io integration websocket mqtt",
            "site:huggingface.co/datasets esp idf code dataset",
        ],
        "trusted_domains": [
            "docs.espressif.com",
            "developers.home-assistant.io",
            "huggingface.co",
        ],
    },
    "power": {
        "topic": "Power electronics / motor control",
        "minimum_web_roots": 8,
        "forum_urls": ELECTRONICS_FORUM_URLS,
        "authoritative_urls": [
            ("TI power management docs", "https://www.ti.com/power-management/overview.html"),
            ("Analog Devices technical articles", "https://www.analog.com/en/technical-articles.html"),
        ],
        "github_repos": [],
        "software_sources": [
            ("ADI Power Studio", "https://www.analog.com/en/resources/evaluation-hardware-and-software/embedded-development-software/power-studio-designer.html"),
            ("TI power management hub", "https://www.ti.com/power-management/overview.html"),
        ],
        "datasheet_roots": [
            ("Analog Devices technical articles", "https://www.analog.com/en/technical-articles.html"),
            ("TI power management documentation", "https://www.ti.com/power-management/overview.html"),
        ],
        "hf_sources": [
            "ksabeh/electronics-dataset",
            "bshada/electronics.stackexchange.com",
            "nick007x/eevblog-posts",
        ],
        "queries": [
            "site:ti.com current mode control compensation application note",
            "site:analog.com buck converter loop stability article",
            "site:huggingface.co/datasets electronics power converter dataset",
        ],
        "trusted_domains": ["ti.com", "analog.com", "huggingface.co"],
    },
    "dsp": {
        "topic": "DSP / signal processing",
        "minimum_web_roots": 8,
        "forum_urls": DSP_FORUM_URLS,
        "authoritative_urls": [
            (
                "CMSIS-DSP docs",
                "https://arm-software.github.io/CMSIS_5/DSP/html/index.html",
            ),
            ("MathWorks signal processing docs", "https://www.mathworks.com/help/signal/"),
        ],
        "github_repos": [
            ("CMSIS_5", "https://github.com/ARM-software/CMSIS_5"),
        ],
        "software_sources": [
            ("CMSIS-DSP docs", "https://arm-software.github.io/CMSIS_5/DSP/html/index.html"),
            ("MathWorks signal processing docs", "https://www.mathworks.com/help/signal/"),
        ],
        "datasheet_roots": [
            ("CMSIS-DSP docs", "https://arm-software.github.io/CMSIS_5/DSP/html/index.html"),
        ],
        "hf_sources": [
            "bshada/electronics.stackexchange.com",
            "common-pile/stackexchange",
            "STEM-AI-mtl/Electrical-engineering",
        ],
        "queries": [
            "site:arm-software.github.io CMSIS DSP FIR FFT example",
            "site:mathworks.com help signal filter design fixed point",
            "site:huggingface.co/datasets dsp stackexchange dataset",
        ],
        "trusted_domains": ["arm-software.github.io", "mathworks.com", "huggingface.co"],
    },
    "emc": {
        "topic": "EMC / EMI / ESD",
        "minimum_web_roots": 8,
        "forum_urls": ELECTRONICS_FORUM_URLS,
        "authoritative_urls": [
            ("TI EMC overview", "https://www.ti.com/interface/emc-overview.html"),
            ("Infineon EMC resources", "https://www.infineon.com/cms/en/design-support/"),
        ],
        "github_repos": [],
        "software_sources": [
            ("TI EMC overview", "https://www.ti.com/interface/emc-overview.html"),
            ("Infineon design support", "https://www.infineon.com/cms/en/design-support/"),
        ],
        "datasheet_roots": [
            ("TI EMC overview", "https://www.ti.com/interface/emc-overview.html"),
            ("Infineon design support", "https://www.infineon.com/cms/en/design-support/"),
        ],
        "hf_sources": [
            "bshada/electronics.stackexchange.com",
            "STEM-AI-mtl/Electrical-engineering",
            "nick007x/eevblog-posts",
        ],
        "queries": [
            "site:ti.com emc layout esd protection application note",
            "site:infineon.com emi filter pcb layout note",
            "site:huggingface.co/datasets electronics emc emi dataset",
        ],
        "trusted_domains": ["ti.com", "infineon.com", "huggingface.co"],
    },
    "kicad": {
        "topic": "KiCad / PCB design",
        "minimum_web_roots": 8,
        "forum_urls": EDA_FORUM_URLS,
        "authoritative_urls": [
            ("KiCad documentation", "https://docs.kicad.org/"),
            ("KiCad forum", "https://forum.kicad.info/"),
            ("Altium documentation", "https://www.altium.com/documentation/"),
            ("EasyEDA docs", "https://docs.easyeda.com/en/"),
        ],
        "github_repos": [
            ("KiCad GitHub org", "https://github.com/KiCad"),
            ("KiCad source mirror", "https://github.com/KiCad/kicad-source-mirror"),
        ],
        "software_sources": [
            ("KiCad source download", "https://www.kicad.org/download/source/"),
            ("KiCad developer docs", "https://dev-docs.kicad.org/"),
            ("Altium Designer docs", "https://www.altium.com/documentation/"),
            ("EasyEDA product", "https://www.easyeda.com/"),
        ],
        "datasheet_roots": [
            ("KiCad library conventions", "https://klc.kicad.org/"),
            ("KiCad libraries", "https://kicad.github.io/"),
            ("EasyEDA libraries management", "https://docs.easyeda.com/en/Introduction/Libraries-Management/"),
        ],
        "hf_sources": [
            "STEM-AI-mtl/Electrical-engineering",
            "bshada/electronics.stackexchange.com",
            "ksabeh/electronics-dataset",
        ],
        "queries": [
            "site:docs.kicad.org differential pair design rules",
            "site:forum.kicad.info footprint courtyard ipc",
            "site:huggingface.co/datasets kicad pcb dataset",
        ],
        "trusted_domains": ["docs.kicad.org", "forum.kicad.info", "huggingface.co"],
    },
    "embedded": {
        "topic": "Embedded systems / ARM / ESP32 / RISC-V",
        "minimum_web_roots": 8,
        "forum_urls": EMBEDDED_FORUM_URLS,
        "authoritative_urls": [
            (
                "ESP-IDF programming guide",
                "https://docs.espressif.com/projects/esp-idf/en/stable/esp32/",
            ),
            ("ST STM32Cube docs", "https://dev.st.com/stm32cube-docs/"),
        ],
        "github_repos": [
            ("esp-idf", "https://github.com/espressif/esp-idf"),
            ("STMicroelectronics org", "https://github.com/STMicroelectronics"),
        ],
        "software_sources": [
            ("ESP-IDF product page", "https://www.espressif.com/en/products/sdks/esp-idf"),
            ("STM32Cube docs", "https://dev.st.com/stm32cube-docs/"),
        ],
        "datasheet_roots": [
            (
                "ESP32 hardware reference",
                "https://docs.espressif.com/projects/esp-idf/en/stable/esp32/hw-reference/index.html",
            ),
            (
                "STM32 MCU documentation",
                "https://www.st.com/en/microcontrollers-microprocessors/stm32-mainstream-mcus/documentation.html",
            ),
        ],
        "hf_sources": [
            "gouthamsk/esp_idf_code",
            "gavmac00/arduino-docs",
            "bshada/arduino.stackexchange.com",
        ],
        "queries": [
            "site:docs.espressif.com esp-idf spi dma cache alignment",
            "site:dev.st.com cortex-m startup linker script dma application note",
            "site:huggingface.co/datasets embedded firmware dataset",
        ],
        "trusted_domains": ["docs.espressif.com", "dev.st.com", "huggingface.co"],
    },
    "platformio": {
        "topic": "PlatformIO / Arduino / ESP32",
        "minimum_web_roots": 8,
        "forum_urls": EMBEDDED_FORUM_URLS,
        "authoritative_urls": [
            ("PlatformIO docs", "https://docs.platformio.org/"),
            (
                "ESP-IDF programming guide",
                "https://docs.espressif.com/projects/esp-idf/en/stable/esp32/",
            ),
        ],
        "github_repos": [
            ("platformio-core", "https://github.com/platformio/platformio-core"),
            ("platformio docs", "https://github.com/platformio/platformio-docs"),
            ("platform-espressif32", "https://github.com/platformio/platform-espressif32"),
            ("esp-idf", "https://github.com/espressif/esp-idf"),
        ],
        "software_sources": [
            ("PlatformIO org", "https://github.com/platformio"),
            ("PlatformIO docs", "https://docs.platformio.org/"),
            ("PlatformIO examples", "https://github.com/platformio/platformio-examples"),
        ],
        "datasheet_roots": [
            (
                "ESP32 hardware reference",
                "https://docs.espressif.com/projects/esp-idf/en/stable/esp32/hw-reference/index.html",
            ),
        ],
        "hf_sources": [
            "gavmac00/arduino-docs",
            "gouthamsk/esp_idf_code",
            "bshada/arduino.stackexchange.com",
        ],
        "queries": [
            "site:docs.platformio.org monitor filters unit testing library_deps",
            "site:docs.espressif.com esp32 ota mqtt platformio",
            "site:huggingface.co/datasets arduino stackexchange dataset",
        ],
        "trusted_domains": ["docs.platformio.org", "docs.espressif.com", "huggingface.co"],
    },
    "freecad": {
        "topic": "FreeCAD / parametric CAD",
        "minimum_web_roots": 8,
        "forum_urls": CAD_FORUM_URLS,
        "authoritative_urls": [
            ("FreeCAD wiki", "https://wiki.freecad.org/"),
            ("FreeCAD project", "https://www.freecad.org/"),
            ("OpenSCAD documentation", "https://openscad.org/documentation.html"),
            ("SOLIDWORKS API Help", "https://help.solidworks.com/"),
            ("Fusion 360 API what's new", "https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/WhatsNew.htm"),
        ],
        "github_repos": [
            ("FreeCAD", "https://github.com/FreeCAD/FreeCAD"),
            ("FreeCAD org", "https://github.com/freecad"),
            ("OpenSCAD", "https://github.com/openscad/openscad"),
            ("CadQuery", "https://github.com/CadQuery/cadquery"),
        ],
        "software_sources": [
            ("FreeCAD project", "https://www.freecad.org/"),
            ("FreeCAD wiki", "https://wiki.freecad.org/"),
            ("OpenSCAD project", "https://openscad.org/"),
            ("CadQuery docs", "https://cadquery.readthedocs.io/"),
            ("Fusion 360 product", "https://www.autodesk.com/products/fusion-360/overview"),
            ("SOLIDWORKS Web Help", "https://help.solidworks.com/"),
        ],
        "datasheet_roots": [
            ("FreeCAD wiki", "https://wiki.freecad.org/"),
            ("OpenSCAD user manual", "https://openscad.org/documentation.html"),
            ("Fusion 360 API reference", "https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/"),
            ("SOLIDWORKS API Help", "https://help.solidworks.com/2024/english/api/sldworksapiprogguide/Welcome.htm"),
        ],
        "hf_sources": ["STEM-AI-mtl/Electrical-engineering"],
        "queries": [
            "site:wiki.freecad.org PartDesign scripting macro",
            "site:www.freecad.org assembly workbench parametric scripting",
            "site:huggingface.co/datasets freecad cad dataset",
            "site:openscad.org documentation parametric cad",
            "site:cadquery.readthedocs.io cadquery workplane examples",
        ],
        "trusted_domains": ["wiki.freecad.org", "freecad.org", "huggingface.co"],
    },
    "components": {
        "topic": "Electronic components / sourcing / libraries / datasheets",
        "minimum_web_roots": 10,
        "forum_urls": ELECTRONICS_FORUM_URLS,
        "authoritative_urls": [
            ("Mouser search help", "https://www.mouser.com/help/search/how-to-search-for-products/"),
            ("Farnell global", "https://www.farnell.com/"),
            ("element14 product search help", "https://in.element14.com/help-searching-for-products"),
            ("DigiKey help", "https://www.digikey.com/en/resources/help"),
            ("Altium documentation", "https://www.altium.com/documentation/"),
            ("EasyEDA libraries management", "https://docs.easyeda.com/en/Introduction/Libraries-Management/"),
        ],
        "github_repos": [],
        "software_sources": [
            ("Mouser search tools", "https://www.mouser.com/searchtools/"),
            ("Farnell datasheets", "https://www.farnell.com/italy/datasheets.html"),
            ("element14", "https://www.element14.com/"),
            ("DigiKey", "https://www.digikey.com/"),
            ("Altium", "https://www.altium.com/documentation/"),
            ("EasyEDA", "https://www.easyeda.com/"),
            ("Octopart", "https://octopart.com/"),
            ("SnapEDA", "https://www.snapeda.com/"),
            ("Ultra Librarian", "https://www.ultralibrarian.com/"),
            ("SamacSys", "https://componentsearchengine.com/"),
            ("LCSC", "https://www.lcsc.com/"),
            ("JLCPCB parts and assembly", "https://jlcpcb.com/parts"),
        ],
        "datasheet_roots": [
            ("Mouser datasheet-oriented search", "https://www.mouser.com/help/search/"),
            ("Farnell datasheets", "https://www.farnell.com/italy/datasheets.html"),
            ("element14 product info and datasheet search", "https://in.element14.com/help-searching-for-products"),
            ("DigiKey datasheets and technical resources", "https://www.digikey.com/en/resources/"),
            ("SnapEDA search", "https://www.snapeda.com/"),
            ("Ultra Librarian search", "https://www.ultralibrarian.com/"),
        ],
        "hf_sources": [
            "bshada/electronics.stackexchange.com",
            "STEM-AI-mtl/Electrical-engineering",
            "nick007x/eevblog-posts",
        ],
        "queries": [
            "site:mouser.com part number datasheet parametric search",
            "site:farnell.com datasheets electronic components",
            "site:element14.com component search datasheet availability",
            "site:digikey.com parametric search datasheet availability",
            "site:altium.com documentation component libraries alternates",
            "site:easyeda.com component library lcsc footprint",
            "site:octopart.com parametric component search alternatives",
        ],
        "trusted_domains": [
            "mouser.com",
            "farnell.com",
            "element14.com",
            "digikey.com",
            "altium.com",
            "easyeda.com",
            "octopart.com",
            "snapeda.com",
            "ultralibrarian.com",
            "componentsearchengine.com",
            "lcsc.com",
            "jlcpcb.com",
        ],
    },
}


def _normalize_url_entries(entries: list[object]) -> list[tuple[str, str]]:
    normalized: list[tuple[str, str]] = []
    for item in entries:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            normalized.append((str(item[0]), str(item[1])))
            continue
        if isinstance(item, dict):
            label = item.get("label")
            url = item.get("url")
            if label and url:
                normalized.append((str(label), str(url)))
    return normalized


def _load_domain_research_overrides(root: Path) -> dict[str, dict]:
    overrides: dict[str, dict] = {}
    if not root.exists():
        return overrides
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        domain = str(payload.get("domain") or path.stem)
        normalized = dict(payload)
        for key in URL_ENTRY_KEYS:
            if key in normalized:
                normalized[key] = _normalize_url_entries(normalized.get(key, []))
        overrides[domain] = normalized
    return overrides


def _merge_domain_research_sources(base: dict[str, dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {domain: dict(metadata) for domain, metadata in base.items()}
    for domain, override in _load_domain_research_overrides(RESEARCH_SOURCES_DIR).items():
        current = dict(merged.get(domain, {}))
        current.update(override)
        merged[domain] = current
    return merged


DOMAIN_RESEARCH = _merge_domain_research_sources(DOMAIN_RESEARCH)


def now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def canonical_domains(domains: list[str], all_domains: bool = False) -> list[str]:
    if all_domains:
        return list(SUPPORTED_DOMAINS)
    resolved: list[str] = []
    for domain in domains:
        if domain not in SUPPORTED_DOMAINS:
            raise SystemExit(f"Unsupported refresh domain: {domain}")
        resolved.append(domain)
    if not resolved:
        raise SystemExit("Provide at least one domain or use --all")
    return resolved


def default_full_datasets_root() -> Path:
    return Path(
        os.environ.get("MASCARADE_FULL_DATASETS_ROOT", str(DEFAULT_FULL_DATASETS_ROOT))
    )


def default_research_dir() -> Path:
    return Path(
        os.environ.get("MASCARADE_DATASET_RESEARCH_DIR", str(DEFAULT_RESEARCH_DIR))
    )


def dataset_path_for(domain: str, dataset_dir: Path | None = None) -> Path:
    return (dataset_dir or DATASETS_DIR) / f"{domain}_chat.jsonl"


def full_dataset_path_for(domain: str, full_datasets_root: Path | None = None) -> Path:
    return (full_datasets_root or default_full_datasets_root()) / f"{domain}_chat.jsonl"


def _run_builder(domain: str, *, with_hf: bool, max_samples: int | None) -> Path:
    builder = seed_builder_for_domain(SCRIPT_DIR, domain)
    if builder is None:
        raise RuntimeError(f"No canonical dataset builder found for {domain}")
    command = [sys.executable, str(builder)]
    if with_hf:
        command.append("--with-hf")
        if max_samples is not None:
            command.extend(["--max-samples", str(max_samples)])
    completed = subprocess.run(command, cwd=SCRIPT_DIR.parent)
    if completed.returncode != 0:
        raise RuntimeError(f"Dataset refresh builder failed for {domain}: {builder.name}")
    return builder


def _source_mode_for_copy(source_path: Path, target_path: Path) -> str:
    try:
        if source_path.resolve() == target_path.resolve():
            return "full_dataset_in_place"
    except FileNotFoundError:
        pass
    return "full_dataset_sync"


def _refresh_from_full_dataset(domain: str, *, target_path: Path, full_datasets_root: Path) -> dict:
    source_path = full_dataset_path_for(domain, full_datasets_root)
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    source_mode = _source_mode_for_copy(source_path, target_path)
    if source_mode != "full_dataset_in_place":
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
    return {
        "mode": source_mode,
        "source_path": str(source_path),
        "builder": None,
    }


def _quality_report_for(path: Path, *, domain: str) -> tuple[dict, int, int]:
    raw_rows = load_jsonl(path)
    normalized_rows, ids_fixed = ensure_row_ids_with_stats(raw_rows, f"{domain}-refresh")
    deduped_rows, duplicates_removed = dedupe_rows_with_stats(normalized_rows)
    if duplicates_removed:
        write_jsonl(path, deduped_rows)
    validation_errors = validate_rows(deduped_rows)
    if validation_errors:
        raise RuntimeError(
            f"Refreshed dataset invalid for {domain}: {len(validation_errors)} errors; "
            f"{validation_errors[0]}"
        )
    report = enforce_dataset_quality(
        deduped_rows,
        label=f"{domain} refreshed dataset",
        ids_fixed=ids_fixed,
    )
    report["duplicates_removed_during_refresh"] = duplicates_removed
    return report, len(deduped_rows), ids_fixed


def _research_payload(domain: str, *, dataset_path: Path, refresh_report: dict) -> dict:
    metadata = DOMAIN_RESEARCH.get(domain, {})
    probe_payload = _ensure_research_probe(domain)
    return {
        "version": 1,
        "generated_at": now_ts(),
        "domain": domain,
        "topic": metadata.get("topic", domain),
        "dataset_path": str(dataset_path),
        "refresh": refresh_report,
        "authoritative_urls": [
            {"label": label, "url": url}
            for label, url in metadata.get("authoritative_urls", [])
        ],
        "github_repos": [
            {"label": label, "url": url}
            for label, url in metadata.get("github_repos", [])
        ],
        "software_sources": [
            {"label": label, "url": url}
            for label, url in metadata.get("software_sources", [])
        ],
        "forum_urls": [
            {"label": label, "url": url}
            for label, url in metadata.get("forum_urls", [])
        ],
        "datasheet_roots": [
            {"label": label, "url": url}
            for label, url in metadata.get("datasheet_roots", [])
        ],
        "hf_sources": [
            {
                "name": item,
                "url": f"https://huggingface.co/datasets/{item}",
            }
            for item in metadata.get("hf_sources", [])
        ],
        "queries": metadata.get("queries", []),
        "trusted_domains": metadata.get("trusted_domains", []),
        "minimum_web_roots": int(metadata.get("minimum_web_roots", 4)),
        "minimum_quality_score": int(metadata.get("minimum_quality_score", 6)),
        "web_probe": probe_payload,
        "legacy_ignored_paths": LEGACY_IGNORED_PATHS,
        "operator_checklist": [
            "sample at least 20 refreshed rows and verify technical plausibility",
            "confirm the newest web findings are represented in prompts/answers",
            "check duplicates and over-long answers before training",
            "record any accepted new sources in the research brief before publish",
        ],
    }


def _validate_research_payload(payload: dict) -> dict:
    authoritative = payload.get("authoritative_urls", [])
    github_repos = payload.get("github_repos", [])
    software_sources = payload.get("software_sources", [])
    forum_urls = payload.get("forum_urls", [])
    datasheet_roots = payload.get("datasheet_roots", [])
    hf_sources = payload.get("hf_sources", [])
    queries = payload.get("queries", [])
    trusted_domains = payload.get("trusted_domains", [])
    web_probe = payload.get("web_probe") or {}

    web_roots_count = (
        len(authoritative)
        + len(github_repos)
        + len(software_sources)
        + len(forum_urls)
        + len(datasheet_roots)
        + len(hf_sources)
    )
    minimum_web_roots = int(payload.get("minimum_web_roots", 4))
    minimum_quality_score = int(payload.get("minimum_quality_score", 6))
    quality_checks = {
        "authoritative_sources": len(authoritative) >= 2,
        "github_or_software_sources": len(github_repos) + len(software_sources) >= 2,
        "forum_coverage": len(forum_urls) >= 4,
        "datasheet_or_vendor_roots": len(datasheet_roots) >= 1,
        "hf_or_dataset_roots": len(hf_sources) >= 1,
        "query_coverage": len(queries) >= 3,
        "trusted_domains_coverage": len(trusted_domains) >= 3,
        "web_root_depth": web_roots_count >= minimum_web_roots,
        "live_web_probe": bool(web_probe) and web_probe.get("status") in {"ok", "partial"},
    }
    quality_score = sum(1 for value in quality_checks.values() if value)
    valid = bool(
        authoritative
        and queries
        and trusted_domains
        and web_roots_count >= minimum_web_roots
        and quality_score >= minimum_quality_score
    )
    return {
        "valid": valid,
        "web_roots_count": web_roots_count,
        "authoritative_count": len(authoritative),
        "github_count": len(github_repos),
        "software_count": len(software_sources),
        "forum_count": len(forum_urls),
        "datasheet_count": len(datasheet_roots),
        "hf_count": len(hf_sources),
        "query_count": len(queries),
        "trusted_domain_count": len(trusted_domains),
        "minimum_web_roots": minimum_web_roots,
        "quality_score": quality_score,
        "minimum_quality_score": minimum_quality_score,
        "quality_checks": quality_checks,
        "web_probe_status": web_probe.get("status"),
        "web_probe_reachable_count": int(web_probe.get("reachable_count", 0)) if web_probe else 0,
        "web_probe_total_count": int(web_probe.get("total_count", 0)) if web_probe else 0,
    }


def _write_research_brief(domain: str, research_dir: Path, payload: dict) -> tuple[Path, Path]:
    research_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = research_dir / f"{domain}_refresh.md"
    json_path = research_dir / f"{domain}_refresh.json"
    lines = [
        f"# Dataset refresh brief: {domain}",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- dataset_path: `{payload['dataset_path']}`",
        f"- source_mode: `{payload['refresh']['source_mode']}`",
        f"- row_count: `{payload['refresh']['row_count']}`",
        f"- quality_status: `{payload['refresh']['quality']['status']}`",
        f"- ids_fixed_in_memory: `{payload['refresh']['ids_fixed']}`",
        f"- duplicates_removed_during_refresh: `{payload['refresh']['quality'].get('duplicates_removed_during_refresh', 0)}`",
        f"- research_valid: `{payload['research_validation']['valid']}`",
        f"- web_roots_count: `{payload['research_validation']['web_roots_count']}`",
        f"- forum_count: `{payload['research_validation']['forum_count']}`",
        f"- quality_score: `{payload['research_validation']['quality_score']}`",
        f"- web_probe_status: `{payload['research_validation'].get('web_probe_status')}`",
        "",
        "## Web research roots",
    ]
    for item in payload["authoritative_urls"]:
        lines.append(f"- [{item['label']}]({item['url']})")
    if payload["hf_sources"]:
        lines.extend(["", "## Hugging Face sources"])
        for item in payload["hf_sources"]:
            lines.append(f"- [{item['name']}]({item['url']})")
    if payload["github_repos"]:
        lines.extend(["", "## Official GitHub sources"])
        for item in payload["github_repos"]:
            lines.append(f"- [{item['label']}]({item['url']})")
    if payload["software_sources"]:
        lines.extend(["", "## Software source roots"])
        for item in payload["software_sources"]:
            lines.append(f"- [{item['label']}]({item['url']})")
    if payload["forum_urls"]:
        lines.extend(["", "## Specialized forums"])
        for item in payload["forum_urls"]:
            lines.append(f"- [{item['label']}]({item['url']})")
    if payload["datasheet_roots"]:
        lines.extend(["", "## Datasheet and vendor roots"])
        for item in payload["datasheet_roots"]:
            lines.append(f"- [{item['label']}]({item['url']})")
    if payload["queries"]:
        lines.extend(["", "## Search queries"])
        for query in payload["queries"]:
            lines.append(f"- `{query}`")
    if payload["trusted_domains"]:
        lines.extend(["", "## Trusted domains"])
        for domain_name in payload["trusted_domains"]:
            lines.append(f"- `{domain_name}`")
    if payload.get("web_probe"):
        lines.extend(["", "## Live web probe"])
        lines.append(f"- status: `{payload['web_probe'].get('status')}`")
        lines.append(
            f"- reachable: `{payload['web_probe'].get('reachable_count', 0)}/{payload['web_probe'].get('total_count', 0)}`"
        )
    lines.extend([
        "",
        "## Legacy ignored by this workflow",
    ])
    for path in payload["legacy_ignored_paths"]:
        lines.append(f"- `{path}`")
    lines.extend(["", "## Operator checklist"])
    for item in payload["operator_checklist"]:
        lines.append(f"- {item}")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return markdown_path, json_path


def refresh_dataset(
    domain: str,
    *,
    dataset_dir: Path | None = None,
    with_hf: bool = False,
    max_samples: int | None = None,
    prefer_full_datasets: bool = True,
    full_datasets_root: Path | None = None,
    research_dir: Path | None = None,
    emit_research_brief: bool = True,
) -> dict:
    if domain not in SUPPORTED_DOMAINS:
        raise RuntimeError(f"Unsupported domain: {domain}")

    target_path = dataset_path_for(domain, dataset_dir)
    full_root = full_datasets_root or default_full_datasets_root()
    refresh_meta: dict[str, object]
    if prefer_full_datasets and full_dataset_path_for(domain, full_root).exists():
        refresh_meta = _refresh_from_full_dataset(
            domain,
            target_path=target_path,
            full_datasets_root=full_root,
        )
    else:
        builder = _run_builder(domain, with_hf=with_hf, max_samples=max_samples)
        canonical_output_path = dataset_path_for(domain, DATASETS_DIR)
        if not canonical_output_path.exists():
            raise RuntimeError(
                f"Dataset refresh builder did not create expected file: {canonical_output_path}"
            )
        if canonical_output_path.resolve() != target_path.resolve():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(canonical_output_path, target_path)
        refresh_meta = {
            "mode": "builder_hf" if with_hf else "builder_seed",
            "source_path": str(builder),
            "builder": builder.name,
        }

    quality_report, row_count, ids_fixed = _quality_report_for(target_path, domain=domain)
    report = {
        "domain": domain,
        "generated_at": now_ts(),
        "target_path": str(target_path),
        "source_mode": refresh_meta["mode"],
        "source_path": refresh_meta["source_path"],
        "builder": refresh_meta["builder"],
        "row_count": row_count,
        "ids_fixed": ids_fixed,
        "duplicates_removed": quality_report.get("duplicates_removed_during_refresh", 0),
        "quality": quality_report,
        "legacy_ignored_paths": LEGACY_IGNORED_PATHS,
    }
    allow_skip_research = _env_flag("MASCARADE_ALLOW_SKIP_WEB_RESEARCH", False)
    if not emit_research_brief and not allow_skip_research:
        raise RuntimeError(
            "Web research is required by the canonical dataset workflow. "
            "Do not use --skip-research-briefs unless MASCARADE_ALLOW_SKIP_WEB_RESEARCH=1 is explicitly set."
        )

    if emit_research_brief:
        payload = _research_payload(domain, dataset_path=target_path, refresh_report=report)
        payload["research_validation"] = _validate_research_payload(payload)
        if not payload["research_validation"]["valid"]:
            raise RuntimeError(
                f"Research brief for {domain} is incomplete: "
                f"{payload['research_validation']['web_roots_count']} web roots, "
                f"{payload['research_validation']['query_count']} queries, "
                f"{payload['research_validation']['trusted_domain_count']} trusted domains, "
                f"quality_score={payload['research_validation']['quality_score']}. "
                f"Minimums: web_roots>={payload['research_validation']['minimum_web_roots']}, "
                f"quality_score>={payload['research_validation']['minimum_quality_score']}."
            )
        md_path, json_path = _write_research_brief(
            domain,
            research_dir or default_research_dir(),
            payload,
        )
        report["research_brief_path"] = str(md_path)
        report["research_json_path"] = str(json_path)
        report["research_validation"] = payload["research_validation"]
    else:
        report["research_brief_path"] = None
        report["research_json_path"] = None
        report["research_validation"] = {
            "valid": False,
            "web_roots_count": 0,
            "authoritative_count": 0,
            "github_count": 0,
            "software_count": 0,
            "datasheet_count": 0,
            "hf_count": 0,
            "query_count": 0,
            "trusted_domain_count": 0,
            "quality_score": 0,
            "minimum_quality_score": 6,
            "quality_checks": {},
        }
    return report


def refresh_domains(
    domains: list[str],
    *,
    dataset_dir: Path | None = None,
    with_hf: bool = False,
    max_samples: int | None = None,
    prefer_full_datasets: bool = True,
    full_datasets_root: Path | None = None,
    research_dir: Path | None = None,
    emit_research_brief: bool = True,
) -> dict[str, dict]:
    reports: dict[str, dict] = {}
    for domain in domains:
        reports[domain] = refresh_dataset(
            domain,
            dataset_dir=dataset_dir,
            with_hf=with_hf,
            max_samples=max_samples,
            prefer_full_datasets=prefer_full_datasets,
            full_datasets_root=full_datasets_root,
            research_dir=research_dir,
            emit_research_brief=emit_research_brief,
        )
    return reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh fine-tuning datasets and emit associated web-research briefs"
    )
    parser.add_argument("domains", nargs="*", help="Supported domains to refresh")
    parser.add_argument("--all", action="store_true", help="Refresh all supported domains")
    parser.add_argument(
        "--dataset-dir",
        default=None,
        help="Optional dataset output directory (defaults to finetune/datasets)",
    )
    parser.add_argument(
        "--with-hf",
        action="store_true",
        help="When falling back to builders, include their Hugging Face enrichment path",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Max samples forwarded to active dataset builders when --with-hf is used",
    )
    parser.add_argument(
        "--prefer-full-datasets",
        action="store_true",
        default=True,
        help="Prefer /mascarade-datasets when present (default: on)",
    )
    parser.add_argument(
        "--no-prefer-full-datasets",
        dest="prefer_full_datasets",
        action="store_false",
        help="Always rebuild from the canonical finetune/datasets/build_* scripts",
    )
    parser.set_defaults(prefer_full_datasets=True)
    parser.add_argument(
        "--full-datasets-root",
        default=None,
        help="Optional path to the full mascarade-datasets repo",
    )
    parser.add_argument(
        "--research-dir",
        default=None,
        help="Directory where web-research briefs will be written",
    )
    parser.add_argument(
        "--skip-research-briefs",
        action="store_true",
        help="Refresh datasets without emitting Markdown/JSON research briefs",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a text summary",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    dataset_dir = None if args.dataset_dir is None else Path(args.dataset_dir).resolve()
    full_datasets_root = (
        None if args.full_datasets_root is None else Path(args.full_datasets_root).resolve()
    )
    research_dir = None if args.research_dir is None else Path(args.research_dir).resolve()
    domains = canonical_domains(args.domains, all_domains=args.all)
    try:
        reports = refresh_domains(
            domains,
            dataset_dir=dataset_dir,
            with_hf=args.with_hf,
            max_samples=args.max_samples,
            prefer_full_datasets=args.prefer_full_datasets,
            full_datasets_root=full_datasets_root,
            research_dir=research_dir,
            emit_research_brief=not args.skip_research_briefs,
        )
    except DatasetQualityError as exc:
        print(f"Dataset refresh quality gate failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Dataset refresh failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
        return 0

    for domain, report in reports.items():
        print(
            f"[REFRESH] {domain}: mode={report['source_mode']} rows={report['row_count']} "
            f"quality={report['quality']['status']}"
        )
        print(
            f"  [RESEARCH] valid={report['research_validation']['valid']} "
            f"web_roots={report['research_validation']['web_roots_count']} "
            f"forums={report['research_validation']['forum_count']} "
            f"queries={report['research_validation']['query_count']} "
            f"trusted_domains={report['research_validation']['trusted_domain_count']} "
            f"quality_score={report['research_validation']['quality_score']}"
        )
        if report["quality"].get("warnings"):
            print(f"  [WARN] {summarize_quality_report(report['quality'])}")
        if report.get("research_brief_path"):
            print(f"  research: {report['research_brief_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
