from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import json
import httpx
from contracts.common import DOM_EVENT_TYPES, CONDITION_OPS


class RuleAgent:
    """Single-agent that uses LLM tool-calling (LangChain if available) to generate triggers.

    If LangChain/OpenAI are unavailable or no token is present, it gracefully falls back to
    a simple deterministic heuristic.
    """

    def __init__(self, api_url: Optional[str] = None, timeout_sec: float = 5.0) -> None:
        self.api_url = (api_url or os.getenv("API_BASE_URL", "http://localhost:4000")).rstrip("/")
        self.timeout = float(os.getenv("AGENT_TIMEOUT_SEC", str(timeout_sec)))
        self.openai_token = os.getenv("OPENAI_TOKEN")

    # --- Tools (sitemap, info, atlas) -------------------------------------------------
    def tool_get_sitemap(self, site_id: str) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(f"{self.api_url}/site/map", params={"siteId": site_id})
            r.raise_for_status()
            data = r.json() or {}
            return data.get("pages", [])

    def tool_get_site_info(self, site_id: str, url: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(f"{self.api_url}/site/info", params={"siteId": site_id, "url": url})
            r.raise_for_status()
            return r.json() or {}

    def tool_get_site_atlas(self, site_id: str, url: str) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(f"{self.api_url}/site/atlas", params={"siteId": site_id, "url": url})
            r.raise_for_status()
            return r.json() or {}

    # --- LLM path --------------------------------------------------------------------
    def _llm_generate(self, site_id: str, rule_instruction: str, output_instruction: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.tools import tool
            from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
        except Exception:
            return None
        if not self.openai_token:
            return None

        # Define tools bound to this instance
        agent_self = self

        @tool("get_sitemap", return_direct=False)
        def get_sitemap(siteId: str) -> List[Dict[str, Any]]:  # type: ignore[override]
            """Fetch the site's sitemap pages array for the given siteId."""
            return agent_self.tool_get_sitemap(siteId)

        @tool("get_site_info", return_direct=False)
        def get_site_info(siteId: str, url: str) -> Dict[str, Any]:  # type: ignore[override]
            """Fetch site info metadata for a specific URL."""
            return agent_self.tool_get_site_info(siteId, url)

        @tool("get_site_atlas", return_direct=False)
        def get_site_atlas(siteId: str, url: str) -> Dict[str, Any]:  # type: ignore[override]
            """Fetch DOM atlas snapshot for a specific URL."""
            return agent_self.tool_get_site_atlas(siteId, url)

        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # small+cheap default
        llm = ChatOpenAI(api_key=self.openai_token, model=model_name, temperature=0)
        llm_tools = [get_sitemap, get_site_info, get_site_atlas]
        llm = llm.bind_tools(llm_tools)

        sys = SystemMessage(
            content=(
                "You are Rule Trigger Agent. Use the available tools to inspect the site map, site info, and DOM atlas. "
                "Derive concrete triggers for the rule instruction. Always output a compact JSON object with key 'triggers' only."
            )
        )
        preferred_events = DOM_EVENT_TYPES

        human = HumanMessage(
            content=json.dumps({
                "siteId": site_id,
                "ruleInstruction": rule_instruction,
                "outputInstruction": output_instruction,
                "requirements": {
                    "eventTypes": preferred_events,
                    "ops": CONDITION_OPS,
                    "fieldExamples": [
                        "telemetry.attributes.path", "telemetry.attributes.id", "telemetry.elementText"
                    ],
                },
                "format": {"triggers": [
                    {"eventType": "page_load", "when": [
                        {"field": "telemetry.attributes.path", "op": "equals", "value": "/cart"},
                        {"field": "telemetry.attributes.id", "op": "equals", "value": "cart-count"},
                        {"field": "telemetry.elementText", "op": "gte", "value": 2}
                    ]}
                ]}
            })
        )

        messages = [sys, human]
        for _ in range(4):  # small loop to resolve tool calls
            ai = llm.invoke(messages)
            tool_calls = getattr(ai, "tool_calls", None) or []
            if not tool_calls:
                # expect final JSON content
                try:
                    data = json.loads(ai.content)
                    trig = data.get("triggers")
                    if isinstance(trig, list):
                        return trig
                except Exception:
                    return None
                return None
            # Append the assistant message that contains tool_calls
            messages.append(ai)
            # Execute tools and append their outputs as ToolMessage responses
            for tc in tool_calls:
                name = tc["name"] if isinstance(tc, dict) else getattr(tc, "name", None)
                args = tc["args"] if isinstance(tc, dict) else getattr(tc, "args", {})
                try:
                    if name == "get_sitemap":
                        result = get_sitemap.invoke(args)
                    elif name == "get_site_info":
                        result = get_site_info.invoke(args)
                    elif name == "get_site_atlas":
                        result = get_site_atlas.invoke(args)
                    else:
                        result = {"error": f"unknown tool {name}"}
                except Exception as e:
                    result = {"error": str(e)}
                messages.append(
                    ToolMessage(
                        content=json.dumps(result)[:4000],
                        tool_call_id=(tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "tool")),
                    )
                )
        return None

    # --- Public API ------------------------------------------------------------------
    def generate_triggers(self, site_id: str, rule_instruction: str, output_instruction: Optional[str] = None) -> List[Dict[str, Any]]:
        # Only LLM agent path; no heuristic fallback
        trig = self._llm_generate(site_id, rule_instruction, output_instruction)
        print(f"Generated triggers: {trig}")
        if isinstance(trig, list) and trig:
            return trig
        raise RuntimeError("AGENT_TRIGGER_GENERATION_FAILED")
