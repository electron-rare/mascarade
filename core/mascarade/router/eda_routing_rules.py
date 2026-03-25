"""EDA routing rules — decide which provider to use for a board."""

from __future__ import annotations


def recommend_provider(
    layer_count: int = 2,
    component_count: int = 0,
    budget: str = "standard",
) -> dict:
    """Recommend an EDA provider based on board characteristics."""
    recommendations = []
    primary = "kicad_router"  # default internal

    # Complexity scoring
    complexity = "simple"
    if layer_count >= 6 or component_count > 200:
        complexity = "complex"
    elif layer_count >= 4 or component_count > 50:
        complexity = "moderate"

    # Analysis always via kicad-happy
    recommendations.append({
        "step": "analyze",
        "provider": "kicad_happy",
        "reason": "Best for schematic analysis, BOM extraction, and DFM checks",
    })

    # Routing
    if complexity == "complex":
        recommendations.append({
            "step": "route",
            "provider": "quilter",
            "reason": f"Complex board ({layer_count}L, {component_count} components) — Quilter RL autorouter recommended",
        })
    elif budget == "fast":
        recommendations.append({
            "step": "route",
            "provider": "pcbdesigner",
            "reason": "Fast budget — PCBDesigner one-click route+order",
        })
    else:
        recommendations.append({
            "step": "route",
            "provider": "kicad_router",
            "reason": f"Standard {complexity} board — internal KiCad router sufficient",
            "alternative": "quilter" if complexity == "moderate" else None,
        })

    # Fabrication
    if budget == "fast":
        recommendations.append({
            "step": "fabricate",
            "provider": "pcbdesigner",
            "reason": "One-click JLCPCB ordering via PCBDesigner",
        })
    else:
        recommendations.append({
            "step": "fabricate",
            "provider": "manual",
            "reason": "Standard flow — review Gerbers before ordering",
        })

    return {
        "complexity": complexity,
        "layer_count": layer_count,
        "component_count": component_count,
        "budget": budget,
        "primary_router": primary,
        "recommendations": recommendations,
    }
