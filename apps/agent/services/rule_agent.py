from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import os
import json
from click import Tuple
import httpx
from contracts.common import DOM_EVENT_TYPES, CONDITION_OPS


class RuleAgent:
    """Single-agent that uses LLM tool-calling (LangChain if available) to generate triggers.

    If LangChain/OpenAI are unavailable or no token is present, it gracefully falls back to
    a simple deterministic heuristic.
    """

    def __init__(self, api_url: Optional[str] = None, timeout_sec: float = 5.0, debug: bool = False) -> None:
        self.api_url = (api_url or os.getenv("API_BASE_URL", "http://localhost:4000")).rstrip("/")
        self.timeout = float(os.getenv("AGENT_TIMEOUT_SEC", str(timeout_sec)))
        self.openai_token = os.getenv("OPENAI_TOKEN")
        self.debug = debug

    # --- Tools (sitemap, info, atlas) -------------------------------------------------
    def tool_get_sitemap(self, site_id: str) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(f"{self.api_url}/site/map", params={"siteId": site_id})
            r.raise_for_status()
            data = r.json() or {}
            return data.get("pages", [])

    def tool_get_site_atlas(self, site_id: str, url: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(f"{self.api_url}/site/atlas", params={"siteId": site_id, "url": url})
            r.raise_for_status()
            return r.json() or {}

    # --- LLM path --------------------------------------------------------------------
    def _llm_generate(self, site_id: str, rule_instruction: str) -> Optional[List[Dict[str, Any]]]:
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.tools import tool
            from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
        except Exception:
            if getattr(self, "debug", False):
                print("[RuleAgent] LangChain/OpenAI not available; skipping LLM path")
            return None
        if not self.openai_token:
            if getattr(self, "debug", False):
                print("[RuleAgent] OPENAI_TOKEN missing; skipping LLM path")
            return None

        # Define tools bound to this instance
        agent_self = self

        @tool("get_sitemap", return_direct=False)
        def get_sitemap(siteId: str) -> List[Dict[str, Any]]:  # type: ignore[override]
            """Fetch the site's sitemap pages array for the given siteId."""
            return agent_self.tool_get_sitemap(siteId)

        @tool("get_site_atlas", return_direct=False)
        def get_site_atlas(siteId: str, url: str) -> Dict[str, Any]:  # type: ignore[override]
            """Fetch DOM atlas snapshot for a specific URL."""
            return agent_self.tool_get_site_atlas(siteId, url)

        model_name = os.getenv("OPENAI_MODEL", "gpt-5-nano")  # small+cheap default
        llm = ChatOpenAI(api_key=self.openai_token, model=model_name, temperature=0)
        llm_tools = [get_sitemap, get_site_atlas]
        llm = llm.bind_tools(llm_tools)

        sys = SystemMessage(
            content=(
                "You are Rule Trigger Agent.\n"
                "Goal: Given a ruleInstruction and a siteId, generate 'triggers' based strictly on real DOM data.\n\n"
                "Step-by-step:\n"
                "1. Call get_sitemap(siteId) to get list of pages.\n"
                "2. Identify candidate page(s) based on ruleInstruction (e.g. keywords like 'cart', 'checkout').\n"
                "3. Call get_site_atlas(siteId, url) for each relevant page to get real DOM elements.\n"
                "4. From those elements, find ones with matching id/class/text relevant to ruleInstruction.\n\n"
                "Use these fields in trigger conditions:\n"
                "- telemetry.attributes.path (equals)\n"
                "- telemetry.attributes.id or .class (equals only)\n"
                "- telemetry.elementText or .attributes.value (for numeric or text comparison)\n\n"
                "Rules:\n"
                "- Do NOT invent IDs or paths. Only use values seen in tool results.\n"
                "- Use 'gte', 'gt', 'lte', 'lt' only on numeric fields like telemetry.elementText.\n"
                "- Bind each trigger to a specific element if possible (via id/class).\n"
                "- Always include telemetry.attributes.path equals <path> from sitemap.\n"
                "- Always return JSON with key 'triggers', and nothing else.\n\n"
                "Example output:\n"
                "{ \"triggers\": [ {\"eventType\": \"page_load\", \"when\": [ ... ]} ] }"
            )
        )
        preferred_events = DOM_EVENT_TYPES

        human = HumanMessage(
            content=json.dumps({
                "siteId": site_id,
                "ruleInstruction": rule_instruction,
                "requirements": {
                    "eventTypes": preferred_events,
                    "ops": CONDITION_OPS,
                    "fieldExamples": [
                        "telemetry.attributes.path", "telemetry.attributes.id", "telemetry.attributes.class", "telemetry.cssPath", "telemetry.elementText"
                    ],
                },
                "outputSchema": {
                    "triggers": [
                        {"eventType": "<one of eventTypes>", "when": [
                            {"field": "<fieldExamples entry>", "op": "<ops entry>", "value": "<value from tools>"}
                        ]}
                    ]
                }
            })
        )

        messages = [sys, human]
        for turn in range(6):  # allow a couple revision cycles
            ai = llm.invoke(messages)
            tool_calls = getattr(ai, "tool_calls", None) or []
            if not tool_calls:
                # expect final JSON content
                try:
                    if self.debug:
                        print(f"[RuleAgent] Final AI content (no tool calls, turn={turn}): {ai.content}")
                    data = _parse_json(ai.content)
                    trig = data.get("triggers")
                    # Lightweight shape check: triggers is a list of dicts
                    if isinstance(trig, list) and all(isinstance(x, dict) for x in trig):
                        return trig
                except Exception:
                    pass
                return []
            messages.append(ai)
            for tc in tool_calls:
                name = tc["name"] if isinstance(tc, dict) else getattr(tc, "name", None)
                args = tc["args"] if isinstance(tc, dict) else getattr(tc, "args", {})
                if isinstance(args, str):
                    try:
                        parsed = json.loads(args)
                        if isinstance(parsed, dict):
                            args = parsed
                    except Exception:
                        pass
                if self.debug:
                    print(f"[RuleAgent] Tool call -> name={name}, args={args}")
                try:
                    if name == "get_sitemap":
                        result = get_sitemap.invoke(args)
                    elif name == "get_site_atlas":
                        result = get_site_atlas.invoke(args)
                    else:
                        result = {"error": f"unknown tool {name}"}
                except Exception as e:
                    result = {"error": str(e)}
                if self.debug:
                    preview = result if isinstance(result, (dict, list)) else str(result)
                    print(f"[RuleAgent] Tool result for {name}: {str(preview)[:200]}")
                messages.append(
                    ToolMessage(
                        content=json.dumps(result)[:4000],
                        tool_call_id=(tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "tool")),
                    )
                )
        return []

    # --- Public API ------------------------------------------------------------------
    def generate_triggers(self, site_id: str, rule_instruction: str) -> List[Dict[str, Any]]:
        """Public API: Generate triggers for a rule instruction using LLM/tool-calling.
        Returns a list of triggers or an empty list if generation failed.
        """
        trig = self._llm_generate(site_id, rule_instruction)
        if self.debug:
            print(f"Generated triggers: {trig}")
        if isinstance(trig, list) and trig:
            return trig
        return []

    # --- Helpers --------------------------------------------------------------------
def _parse_json(text: str) -> Dict[str, Any]:
    """Parse a JSON object from a string, or return empty dict on failure."""
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {}

