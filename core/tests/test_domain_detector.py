"""Tests pour le détecteur de domaine."""

from mascarade.router.domain_detector import DomainDetector


def test_detect_kicad_domain():
    """Détecte le domaine KiCAD à partir de mots-clés."""
    detector = DomainDetector()
    text = "I need help designing a PCB schematic in KiCAD"
    assert detector.detect_domain(text) == "kicad"


def test_detect_spice_domain():
    """Détecte le domaine SPICE à partir de mots-clés."""
    detector = DomainDetector()
    text = "Run a transient simulation in ngspice with this circuit"
    assert detector.detect_domain(text) == "spice"


def test_detect_freecad_domain():
    """Détecte le domaine FreeCAD à partir de mots-clés."""
    detector = DomainDetector()
    text = "Create a parametric 3D model in FreeCAD with constraints"
    assert detector.detect_domain(text) == "freecad"


def test_detect_stm32_domain():
    """Détecte le domaine STM32 à partir de mots-clés."""
    detector = DomainDetector()
    text = "Configure UART and GPIO on STM32 using HAL"
    assert detector.detect_domain(text) == "stm32"


def test_detect_iot_domain():
    """Détecte le domaine IoT à partir de mots-clés."""
    detector = DomainDetector()
    text = "Setup MQTT on ESP32 for sensor data"
    assert detector.detect_domain(text) == "iot"


def test_detect_general_when_empty():
    """Retourne 'general' pour texte vide."""
    detector = DomainDetector()
    assert detector.detect_domain("") == "general"
    assert detector.detect_domain(None) == "general"


def test_detect_general_when_no_keywords():
    """Retourne 'general' quand aucun mot-clé ne matche."""
    detector = DomainDetector()
    text = "Hello, how are you today?"
    assert detector.detect_domain(text) == "general"


def test_case_insensitive_detection():
    """La détection est insensible à la casse."""
    detector = DomainDetector()
    assert detector.detect_domain("KICAD PCB") == "kicad"
    assert detector.detect_domain("KiCaD pCb") == "kicad"
    assert detector.detect_domain("kicad pcb") == "kicad"


def test_multiple_keyword_occurrences():
    """Compte correctement les occurrences multiples."""
    detector = DomainDetector()
    # Texte avec plusieurs occurrences de mots-clés KiCAD
    text = "kicad pcb schematic pcb footprint pcb"
    assert detector.detect_domain(text) == "kicad"


def test_highest_score_wins():
    """Le domaine avec le score le plus élevé gagne."""
    detector = DomainDetector()
    # Texte avec des mots-clés IoT (3) vs STM32 (1)
    text = "ESP32 with MQTT and sensor using I2C"
    domain = detector.detect_domain(text)
    # "esp32" (iot), "mqtt" (iot), "sensor" (iot), "i2c" (stm32)
    assert domain == "iot"


def test_mixed_domains_kicad_wins():
    """Quand plusieurs domaines matchent, le plus fort gagne."""
    detector = DomainDetector()
    # Beaucoup de mots KiCAD, un seul mot SPICE
    text = "kicad pcb schematic footprint netlist with a resistor"
    assert detector.detect_domain(text) == "kicad"


def test_get_model_for_kicad():
    """Retourne le bon modèle pour le domaine KiCAD."""
    detector = DomainDetector()
    assert detector.get_model_for_domain("kicad") == "mascarade-kicad"


def test_get_model_for_spice():
    """Retourne le bon modèle pour le domaine SPICE."""
    detector = DomainDetector()
    assert detector.get_model_for_domain("spice") == "mascarade-spice"


def test_get_model_for_freecad():
    """Retourne le bon modèle pour le domaine FreeCAD."""
    detector = DomainDetector()
    assert detector.get_model_for_domain("freecad") == "mascarade-freecad"


def test_get_model_for_stm32():
    """Retourne le modèle IoT pour le domaine STM32."""
    detector = DomainDetector()
    assert detector.get_model_for_domain("stm32") == "mascarade-iot"


def test_get_model_for_iot():
    """Retourne le bon modèle pour le domaine IoT."""
    detector = DomainDetector()
    assert detector.get_model_for_domain("iot") == "mascarade-iot"


def test_get_model_for_general():
    """Retourne None pour le domaine general."""
    detector = DomainDetector()
    assert detector.get_model_for_domain("general") is None


def test_get_model_for_unknown_domain():
    """Retourne None pour un domaine inconnu."""
    detector = DomainDetector()
    assert detector.get_model_for_domain("unknown") is None


def test_supported_domains_list():
    """Retourne la liste complète des domaines supportés."""
    detector = DomainDetector()
    domains = detector.supported_domains
    assert "kicad" in domains
    assert "spice" in domains
    assert "freecad" in domains
    assert "stm32" in domains
    assert "iot" in domains
    assert len(domains) == 5


def test_detect_with_mixed_case_keywords():
    """Détecte correctement avec des mots-clés en casse mixte."""
    detector = DomainDetector()
    text = "Using PcbNew in KiCad for routing traces and vias"
    assert detector.detect_domain(text) == "kicad"


def test_detect_spice_with_circuit_analysis():
    """Détecte SPICE avec vocabulaire d'analyse de circuit."""
    detector = DomainDetector()
    text = "AC analysis of opamp circuit with capacitor and resistor"
    assert detector.detect_domain(text) == "spice"


def test_detect_freecad_with_cad_terms():
    """Détecte FreeCAD avec termes CAD."""
    detector = DomainDetector()
    text = "Extrude the sketch and add a fillet to the edge"
    assert detector.detect_domain(text) == "freecad"


def test_detect_stm32_with_peripherals():
    """Détecte STM32 avec noms de périphériques."""
    detector = DomainDetector()
    text = "Configure ADC, timer and DMA on Cortex-M microcontroller"
    assert detector.detect_domain(text) == "stm32"


def test_detect_iot_with_protocols():
    """Détecte IoT avec protocoles de communication."""
    detector = DomainDetector()
    text = "Arduino with LoRaWAN and Bluetooth sensors"
    assert detector.detect_domain(text) == "iot"


def test_partial_keyword_match():
    """Les mots-clés peuvent être des sous-chaînes."""
    detector = DomainDetector()
    # "specification" ne contient pas "spice", donc retourne general
    text = "Write a specification document"
    assert detector.detect_domain(text) == "general"
    # Mais "spice-based circuit" contient "spice" et matchera
    text2 = "A spice-based circuit simulation"
    assert detector.detect_domain(text2) == "spice"


def test_whitespace_handling():
    """Gère correctement les espaces et sauts de ligne."""
    detector = DomainDetector()
    text = """
    Design a PCB layout
    in KiCAD with proper
    routing and footprints
    """
    assert detector.detect_domain(text) == "kicad"


def test_empty_domain_scores():
    """Quand aucun score n'est calculé, retourne general."""
    detector = DomainDetector()
    text = "This text has no technical keywords at all"
    assert detector.detect_domain(text) == "general"


def test_single_keyword_detection():
    """Un seul mot-clé suffit pour la détection."""
    detector = DomainDetector()
    assert detector.detect_domain("gerber") == "kicad"
    assert detector.detect_domain("mosfet") == "spice"
    assert detector.detect_domain("chamfer") == "freecad"
    assert detector.detect_domain("cubemx") == "stm32"
    assert detector.detect_domain("zigbee") == "iot"
