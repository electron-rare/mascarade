#!/usr/bin/env python3
"""
Verify templates structure without running full services
"""

import sys
from pathlib import Path

# Add core to path
sys.path.insert(0, str(Path(__file__).parent / "core"))

# Import only what we need - avoid full dependency tree
import importlib.util

spec = importlib.util.spec_from_file_location(
    "templates",
    Path(__file__).parent / "core" / "mascarade" / "orchestrator" / "templates.py",
)
templates = importlib.util.module_from_spec(spec)


# Manually define the minimal dependencies
class BaseModel:
    """Minimal Pydantic BaseModel stub"""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def model_dump(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


# Mock the dependencies that templates.py needs
sys.modules["pydantic"] = type(sys)("pydantic")
sys.modules["pydantic"].BaseModel = BaseModel
sys.modules["pydantic"].Field = lambda **kwargs: None

# Now we can load the module
spec.loader.exec_module(templates)

# Verify templates
print("=== Template Verification ===\n")

builtin_templates = templates.BUILTIN_TEMPLATES
print(f"✓ Found {len(builtin_templates)} built-in templates")

required_templates = {
    "code-review-workflow": "Code Review",
    "research-report": "Research",
    "translate-and-polish": "Translation",
    "electronics-pipeline": "Electronics",
}

found_templates = {}
for template in builtin_templates:
    template_data = {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "agents": template.agent_names,
        "mode": str(template.mode),
        "has_documentation": len(template.documentation) > 0,
    }
    found_templates[template.id] = template_data
    print(f"\nTemplate: {template.id}")
    print(f"  Name: {template.name}")
    print(f"  Agents: {', '.join(template.agent_names)}")
    print(f"  Mode: {template.mode}")
    print(f"  Documentation: {len(template.documentation)} chars")

print("\n=== Acceptance Criteria Check ===\n")

# Check 1: At least 4 templates
if len(builtin_templates) >= 4:
    print("✓ PASS: At least 4 templates available")
else:
    print(f"✗ FAIL: Only {len(builtin_templates)} templates (need 4+)")
    sys.exit(1)

# Check 2: Required templates present
all_required_present = True
for template_id, category in required_templates.items():
    if template_id in found_templates:
        print(f"✓ PASS: {category} template '{template_id}' found")
    else:
        print(f"✗ FAIL: {category} template '{template_id}' missing")
        all_required_present = False

if not all_required_present:
    sys.exit(1)

# Check 3: Electronics template has correct agents
electronics = found_templates.get("electronics-pipeline")
if electronics:
    expected_agents = {"kicad-designer", "spice-expert", "components-expert"}
    actual_agents = set(electronics["agents"])
    if expected_agents == actual_agents:
        print(
            f"✓ PASS: Electronics template uses correct agents: {', '.join(expected_agents)}"
        )
    else:
        print("✗ FAIL: Electronics agents mismatch")
        print(f"  Expected: {expected_agents}")
        print(f"  Actual: {actual_agents}")
        sys.exit(1)

# Check 4: All templates have documentation
missing_docs = []
for template_id, data in found_templates.items():
    if not data["has_documentation"]:
        missing_docs.append(template_id)

if not missing_docs:
    print("✓ PASS: All templates have documentation")
else:
    print(f"✗ FAIL: Templates missing documentation: {', '.join(missing_docs)}")
    sys.exit(1)

# Check 5: Code review template present
if "code-review-workflow" in found_templates:
    print("✓ PASS: Code review template available for deployment")
else:
    print("✗ FAIL: Code review template missing")
    sys.exit(1)

print("\n=== All Checks Passed ✓ ===")
print("\nSummary:")
print(f"  Total templates: {len(builtin_templates)}")
print("  Required templates: All present")
print("  Electronics agents: Correct (kicad-designer, spice-expert, components-expert)")
print("  Documentation: All templates documented")

print("\n=== Next Steps ===")
print("To test deployment, start the services:")
print(
    "  1. cd core && source .venv/bin/activate && python -m uvicorn mascarade.server:app --reload --port 8100"
)
print("  2. cd api && npm run dev")
print("  3. Run ./test_templates_e2e.sh")
