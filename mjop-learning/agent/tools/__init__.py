"""Register van agent-tools. Elke tool is alleen-lezen en heeft een JSON Schema voor invoer en uitvoer."""
from agent.contract import ToolError
from agent.tools import get_kengetal_candidates as _gkc

TOOLS = {
    _gkc.NAME: {"function": _gkc.get_kengetal_candidates, "spec": _gkc.TOOL_SPEC},
}


def tool_specs():
    """Modelonafhankelijke toolbeschrijvingen: {name, description, input_schema} (JSON Schema)."""
    return [dict(TOOLS[name]["spec"]) for name in sorted(TOOLS)]


def call_tool(name, arguments):
    """Enige ingang voor een model/agent. Geeft alleen de argumenten door; de gegevensroot kan hier niet worden
    gekozen (geen pad-parameter)."""
    if name not in TOOLS:
        raise ToolError("UNKNOWN_TOOL", f"onbekende tool: {name!r}")
    return TOOLS[name]["function"](arguments)
