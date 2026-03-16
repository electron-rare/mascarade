#!/usr/bin/env bash
#
# generate_api_docs.sh - Generate static API reference documentation
#
# This script generates comprehensive Markdown API reference documentation
# from the FastAPI router files at docs/api/README.md
#
# Usage:
#   bash scripts/generate_api_docs.sh
#
# Output:
#   docs/api/README.md - Static API reference documentation
#

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Generating API Documentation ===${NC}"

# Generate the documentation using Python
echo -e "${YELLOW}Generating documentation from router files...${NC}"
python3 << 'PYTHON_SCRIPT'
import re
import sys
from pathlib import Path


def parse_router_file(file_path: Path) -> list:
    """Parse a router file to extract endpoint information."""
    content = file_path.read_text()

    endpoints = []

    # Find router prefix if it exists
    prefix_match = re.search(r'router = APIRouter\(prefix="([^"]*)"', content)
    prefix = prefix_match.group(1) if prefix_match else ""

    # Find all route decorators and their functions
    # Pattern matches: @router.METHOD("path") followed by async def and docstring
    pattern = r'@router\.(get|post|put|delete|patch)\("([^"]+)"[^)]*\)\s*\n\s*async def (\w+)\([^)]*\).*?:\s*\n\s*"""(.*?)"""'
    matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)

    for match in matches:
        method, path, func_name, docstring = match.groups()
        # Clean up docstring - remove leading/trailing whitespace from each line
        doc_lines = docstring.strip().split('\n')
        doc_lines = [line.strip() for line in doc_lines]
        # Get first paragraph (before Args/Returns/Raises)
        clean_doc = []
        for line in doc_lines:
            if line.startswith('Args:') or line.startswith('Returns:') or line.startswith('Raises:'):
                break
            if line:
                clean_doc.append(line)

        docstring_clean = ' '.join(clean_doc) if clean_doc else docstring.strip()

        # Combine prefix with path
        full_path = prefix + path if prefix else path

        endpoints.append({
            "method": method.upper(),
            "path": full_path,
            "function": func_name,
            "docstring": docstring_clean
        })

    return endpoints


def generate_markdown_docs() -> str:
    """Generate Markdown documentation from router files."""
    lines = []

    # Header
    lines.append("# Mascarade Core API Documentation")
    lines.append("")
    lines.append("**Version:** 0.1.0")
    lines.append("")
    lines.append("Personal agentic orchestration system - Python core API")
    lines.append("")
    lines.append("Provides LLM routing, agent orchestration, memory management, and OpenAI-compatible chat completions.")
    lines.append("")

    # Base URL
    lines.append("## Base URL")
    lines.append("")
    lines.append("```")
    lines.append("http://localhost:8100")
    lines.append("```")
    lines.append("")

    # Find all router files
    router_dir = Path("core/mascarade/routers")
    router_files = {
        "health.py": "Health",
        "auth.py": "Authentication",
        "chat.py": "Chat Completions",
        "agents.py": "Agents",
        "memory.py": "Memory",
        "providers.py": "Providers",
    }

    lines.append("## Endpoints")
    lines.append("")

    for filename, category in router_files.items():
        file_path = router_dir / filename
        if not file_path.exists():
            continue

        lines.append(f"### {category}")
        lines.append("")

        endpoints = parse_router_file(file_path)

        if not endpoints:
            lines.append("*No endpoints found*")
            lines.append("")
            continue

        for endpoint in endpoints:
            method = endpoint["method"]
            path = endpoint["path"]
            docstring = endpoint["docstring"]

            # Endpoint header
            lines.append(f"#### `{method} {path}`")
            lines.append("")

            # Description from docstring
            # Split docstring into lines and format
            doc_lines = [line.strip() for line in docstring.split('\n') if line.strip()]
            for line in doc_lines[:3]:  # First 3 lines
                lines.append(line)
            lines.append("")

            lines.append("---")
            lines.append("")

    # Footer
    lines.append("## Additional Information")
    lines.append("")
    lines.append("### Interactive Documentation")
    lines.append("")
    lines.append("For complete API documentation with request/response schemas and interactive testing:")
    lines.append("")
    lines.append("- **Swagger UI**: http://localhost:8100/docs")
    lines.append("- **ReDoc**: http://localhost:8100/redoc")
    lines.append("- **OpenAPI Spec**: http://localhost:8100/openapi.json")
    lines.append("")
    lines.append("### Authentication")
    lines.append("")
    lines.append("Most endpoints require authentication. Include your API key in the request headers:")
    lines.append("")
    lines.append("```")
    lines.append("Authorization: Bearer <your-api-key>")
    lines.append("```")
    lines.append("")
    lines.append("### Key Features")
    lines.append("")
    lines.append("- **LLM Provider Routing**: Intelligent routing to multiple LLM providers (OpenAI, Anthropic, Mistral, etc.)")
    lines.append("- **Agent Orchestration**: Create and manage specialized AI agents with custom prompts and capabilities")
    lines.append("- **Memory Layer**: Persistent conversation memory via Mem0 integration")
    lines.append("- **OpenAI Compatibility**: Drop-in replacement for OpenAI API endpoints")
    lines.append("- **Health Monitoring**: Real-time provider health checks and failover")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Generated automatically from router source files*")

    return "\n".join(lines)


def main():
    """Main function to generate API documentation."""
    try:
        # Generate Markdown documentation
        markdown_content = generate_markdown_docs()

        # Write to file
        output_path = Path("docs/api/README.md")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown_content)

        print(f"✓ API documentation generated successfully")

    except Exception as e:
        print(f"✗ Error generating API documentation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
PYTHON_SCRIPT

echo -e "${GREEN}✓ API documentation generated at docs/api/README.md${NC}"
echo ""
echo "View the documentation:"
echo "  - Markdown: $PROJECT_ROOT/docs/api/README.md"
echo "  - Swagger UI: http://localhost:8100/docs (when server is running)"
echo "  - ReDoc: http://localhost:8100/redoc (when server is running)"
