"""MJOP AI-agent, fase 1: alleen-lezen tools bovenop de bestaande deterministische pipeline.

Zie docs/agent_tools_v1.md. Dit pakket bevat geen modelaanroepen, geen netwerk en geen schrijfpad; de
toolcontracten zijn JSON Schema's en dus onafhankelijk van een bepaald model of agent-framework.
"""
from agent.tools import TOOLS, call_tool, tool_specs  # noqa: F401
