"""Test prompts suite for benchmarking model performance across different domains."""

# Domain-specific test prompts
TEST_PROMPTS = {
    "electronics": [
        {
            "id": "elec-001",
            "difficulty": "medium",
            "prompt": "Design a voltage divider circuit that steps down 12V to 5V with a load current of 100mA. Calculate the required resistor values and power ratings.",
            "expected_elements": [
                "resistor calculations",
                "power dissipation",
                "load consideration",
            ],
        },
        {
            "id": "elec-002",
            "difficulty": "hard",
            "prompt": "Design a low-pass RC filter with a cutoff frequency of 1kHz and input impedance of at least 10kΩ. Provide component values and explain the frequency response.",
            "expected_elements": [
                "cutoff frequency calculation",
                "RC values",
                "frequency response",
                "impedance",
            ],
        },
        {
            "id": "elec-003",
            "difficulty": "medium",
            "prompt": "Explain the differences between BJT and MOSFET transistors in terms of switching speed, power consumption, and typical applications.",
            "expected_elements": [
                "BJT characteristics",
                "MOSFET characteristics",
                "comparison",
                "applications",
            ],
        },
        {
            "id": "elec-004",
            "difficulty": "hard",
            "prompt": "Design a 555 timer circuit in astable mode to generate a 1kHz square wave with 60% duty cycle. Calculate component values.",
            "expected_elements": [
                "555 timer",
                "frequency calculation",
                "duty cycle",
                "component values",
            ],
        },
        {
            "id": "elec-005",
            "difficulty": "easy",
            "prompt": "Calculate the total capacitance of three capacitors in parallel: 10μF, 22μF, and 47μF.",
            "expected_elements": ["parallel capacitance", "calculation", "result"],
        },
    ],
    "spice": [
        {
            "id": "spice-001",
            "difficulty": "medium",
            "prompt": "Generate a SPICE netlist for a simple voltage divider with R1=10kΩ, R2=5kΩ, and Vin=12V. Include DC analysis.",
            "expected_elements": [
                "netlist syntax",
                "resistor definitions",
                "voltage source",
                ".dc analysis",
            ],
        },
        {
            "id": "spice-002",
            "difficulty": "hard",
            "prompt": "Create a SPICE netlist for an RC low-pass filter (R=1kΩ, C=100nF) with AC analysis from 1Hz to 100kHz. Include .control directives to plot magnitude and phase.",
            "expected_elements": [
                "AC analysis",
                ".ac directive",
                ".control section",
                "plotting commands",
            ],
        },
        {
            "id": "spice-003",
            "difficulty": "hard",
            "prompt": "Debug this convergence issue: A SPICE simulation fails with 'timestep too small' error in a transient analysis. What are the common causes and fixes?",
            "expected_elements": [
                "convergence issues",
                "timestep problems",
                "solutions",
                "SPICE options",
            ],
        },
        {
            "id": "spice-004",
            "difficulty": "medium",
            "prompt": "Generate a SPICE netlist for a common-emitter amplifier using a 2N2222 transistor with appropriate biasing. Include transient analysis.",
            "expected_elements": [
                "BJT model",
                "biasing network",
                ".tran analysis",
                "proper component values",
            ],
        },
        {
            "id": "spice-005",
            "difficulty": "easy",
            "prompt": "Write a SPICE voltage source that generates a 1kHz, 5V amplitude sine wave.",
            "expected_elements": [
                "VSIN syntax",
                "frequency",
                "amplitude",
                "correct format",
            ],
        },
    ],
    "kicad": [
        {
            "id": "kicad-001",
            "difficulty": "medium",
            "prompt": "Explain the workflow for creating a custom footprint in KiCad for an SMD component with a unique pad layout.",
            "expected_elements": [
                "footprint editor",
                "pad creation",
                "courtyard",
                "3D model",
            ],
        },
        {
            "id": "kicad-002",
            "difficulty": "hard",
            "prompt": "Design a 4-layer PCB stackup for a mixed-signal board with analog and digital sections. Specify layer purposes and provide design rules.",
            "expected_elements": [
                "layer stackup",
                "signal/power planes",
                "analog/digital separation",
                "design rules",
            ],
        },
        {
            "id": "kicad-003",
            "difficulty": "medium",
            "prompt": "How do you properly set up differential pair routing in KiCad for USB 2.0 signals? Include impedance considerations.",
            "expected_elements": [
                "differential pairs",
                "routing rules",
                "impedance control",
                "USB requirements",
            ],
        },
        {
            "id": "kicad-004",
            "difficulty": "easy",
            "prompt": "Explain the difference between KiCad's schematic symbols and footprints, and how they are linked.",
            "expected_elements": [
                "symbols vs footprints",
                "association",
                "library structure",
            ],
        },
        {
            "id": "kicad-005",
            "difficulty": "hard",
            "prompt": "Design a power supply section schematic in KiCad for a 5V/3.3A buck converter using TPS54335A. Include all necessary support components.",
            "expected_elements": [
                "buck converter",
                "component selection",
                "feedback network",
                "input/output caps",
            ],
        },
    ],
    "stm32": [
        {
            "id": "stm32-001",
            "difficulty": "medium",
            "prompt": "Configure UART1 on STM32F4 to transmit at 115200 baud with 8N1 settings using HAL. Provide initialization code.",
            "expected_elements": [
                "HAL_UART",
                "configuration struct",
                "initialization",
                "baud rate setup",
            ],
        },
        {
            "id": "stm32-002",
            "difficulty": "hard",
            "prompt": "Implement a DMA-based SPI transfer on STM32F4 to read data from an external ADC at 1MHz. Include proper interrupt handling.",
            "expected_elements": [
                "DMA configuration",
                "SPI setup",
                "interrupt handlers",
                "buffer management",
            ],
        },
        {
            "id": "stm32-003",
            "difficulty": "medium",
            "prompt": "Explain the difference between STM32's Standard Peripheral Library (SPL) and HAL, and when to use each.",
            "expected_elements": [
                "SPL characteristics",
                "HAL characteristics",
                "comparison",
                "use cases",
            ],
        },
        {
            "id": "stm32-004",
            "difficulty": "hard",
            "prompt": "Configure a PWM output on TIM2 Channel 1 (STM32F4) to generate a 20kHz signal with 50% duty cycle. Provide complete initialization code.",
            "expected_elements": [
                "timer configuration",
                "PWM mode",
                "prescaler/period calculation",
                "HAL code",
            ],
        },
        {
            "id": "stm32-005",
            "difficulty": "easy",
            "prompt": "How do you toggle a GPIO pin (PA5) on STM32 using HAL?",
            "expected_elements": ["GPIO HAL functions", "pin toggle", "correct syntax"],
        },
        {
            "id": "stm32-006",
            "difficulty": "hard",
            "prompt": "Implement low-power mode on STM32L4 to achieve <10μA current consumption in stop mode, with wakeup from RTC alarm.",
            "expected_elements": [
                "low-power modes",
                "RTC configuration",
                "wakeup sources",
                "power optimization",
            ],
        },
    ],
    "code": [
        {
            "id": "code-001",
            "difficulty": "medium",
            "prompt": "Write a Python function to implement a circular buffer (ring buffer) with fixed size. Include enqueue, dequeue, and is_full methods.",
            "expected_elements": [
                "class structure",
                "buffer management",
                "wraparound logic",
                "edge cases",
            ],
        },
        {
            "id": "code-002",
            "difficulty": "hard",
            "prompt": "Implement a rate limiter in Python using the token bucket algorithm. It should limit requests to 100/minute with burst capacity of 10.",
            "expected_elements": [
                "token bucket",
                "time tracking",
                "thread safety",
                "rate limiting logic",
            ],
        },
        {
            "id": "code-003",
            "difficulty": "medium",
            "prompt": "Write a recursive function to calculate the nth Fibonacci number with memoization to optimize performance.",
            "expected_elements": [
                "recursion",
                "memoization",
                "base cases",
                "optimization",
            ],
        },
        {
            "id": "code-004",
            "difficulty": "easy",
            "prompt": "Write a Python function to check if a string is a valid IPv4 address.",
            "expected_elements": [
                "input validation",
                "octet checking",
                "range validation",
                "format check",
            ],
        },
        {
            "id": "code-005",
            "difficulty": "hard",
            "prompt": "Implement an async HTTP client in Python using httpx that retries failed requests with exponential backoff (max 3 retries).",
            "expected_elements": [
                "async/await",
                "httpx usage",
                "retry logic",
                "exponential backoff",
            ],
        },
        {
            "id": "code-006",
            "difficulty": "medium",
            "prompt": "Write a Python decorator that measures and logs the execution time of a function.",
            "expected_elements": [
                "decorator syntax",
                "time measurement",
                "logging",
                "function wrapping",
            ],
        },
    ],
    "general": [
        {
            "id": "gen-001",
            "difficulty": "easy",
            "prompt": "Explain the difference between analog and digital signals with practical examples.",
            "expected_elements": [
                "analog definition",
                "digital definition",
                "examples",
                "comparison",
            ],
        },
        {
            "id": "gen-002",
            "difficulty": "medium",
            "prompt": "What is I2C protocol? Explain its key features, advantages, and typical use cases in embedded systems.",
            "expected_elements": [
                "I2C basics",
                "protocol features",
                "advantages",
                "applications",
            ],
        },
        {
            "id": "gen-003",
            "difficulty": "medium",
            "prompt": "Describe the software development lifecycle (SDLC) and its main phases.",
            "expected_elements": [
                "SDLC phases",
                "requirements",
                "design",
                "testing",
                "deployment",
            ],
        },
        {
            "id": "gen-004",
            "difficulty": "easy",
            "prompt": "What is the purpose of a pull-up resistor in digital circuits?",
            "expected_elements": [
                "pull-up function",
                "default state",
                "use cases",
                "typical values",
            ],
        },
        {
            "id": "gen-005",
            "difficulty": "hard",
            "prompt": "Explain the concept of interrupt priority and nesting in embedded systems. How does it improve real-time performance?",
            "expected_elements": [
                "interrupt priority",
                "nesting",
                "NVIC",
                "real-time benefits",
            ],
        },
        {
            "id": "gen-006",
            "difficulty": "medium",
            "prompt": "What are the main differences between HTTP/1.1, HTTP/2, and HTTP/3?",
            "expected_elements": [
                "HTTP/1.1 features",
                "HTTP/2 improvements",
                "HTTP/3 QUIC",
                "comparison",
            ],
        },
    ],
}


def get_test_prompts(domain: str, difficulty: str | None = None) -> list[dict[str, str]]:
    """
    Retrieve test prompts for a specific domain.

    Args:
        domain: Domain name (electronics, spice, kicad, stm32, code, general)
        difficulty: Optional filter by difficulty (easy, medium, hard)

    Returns:
        List of test prompt dictionaries

    Raises:
        ValueError: If domain is not recognized
    """
    if domain not in TEST_PROMPTS:
        raise ValueError(
            f"Unknown domain '{domain}'. Available domains: {', '.join(TEST_PROMPTS.keys())}"
        )

    prompts = TEST_PROMPTS[domain]

    if difficulty:
        prompts = [p for p in prompts if p.get("difficulty") == difficulty.lower()]

    return prompts


def get_all_domains() -> list[str]:
    """
    Get list of all available benchmark domains.

    Returns:
        List of domain names
    """
    return list(TEST_PROMPTS.keys())


def get_prompt_by_id(prompt_id: str) -> dict[str, str] | None:
    """
    Retrieve a specific test prompt by its ID.

    Args:
        prompt_id: Unique prompt identifier (e.g., 'elec-001')

    Returns:
        Prompt dictionary if found, None otherwise
    """
    for domain_prompts in TEST_PROMPTS.values():
        for prompt in domain_prompts:
            if prompt["id"] == prompt_id:
                return prompt
    return None


def get_all_prompts() -> list[dict[str, str]]:
    """
    Retrieve all test prompts across all domains.

    Returns:
        List of all test prompt dictionaries
    """
    all_prompts = []
    for prompts in TEST_PROMPTS.values():
        all_prompts.extend(prompts)
    return all_prompts


def get_prompts_by_difficulty(difficulty: str) -> list[dict[str, str]]:
    """
    Retrieve all prompts matching a specific difficulty level.

    Args:
        difficulty: Difficulty level (easy, medium, hard)

    Returns:
        List of matching test prompt dictionaries
    """
    difficulty = difficulty.lower()
    matching_prompts = []

    for prompts in TEST_PROMPTS.values():
        matching_prompts.extend([p for p in prompts if p.get("difficulty") == difficulty])

    return matching_prompts


# Example usage
if __name__ == "__main__":
    # Test retrieval
    electronics_prompts = get_test_prompts("electronics")
    print(f"Electronics prompts: {len(electronics_prompts)}")

    # Filter by difficulty
    hard_prompts = get_test_prompts("electronics", difficulty="hard")
    print(f"Hard electronics prompts: {len(hard_prompts)}")

    # Get all domains
    domains = get_all_domains()
    print(f"Available domains: {domains}")

    # Get specific prompt
    prompt = get_prompt_by_id("spice-001")
    if prompt:
        print(f"Found prompt: {prompt['id']} - {prompt['prompt'][:50]}...")

    # Get all prompts
    all_prompts = get_all_prompts()
    print(f"Total prompts across all domains: {len(all_prompts)}")
