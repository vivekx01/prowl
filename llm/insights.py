import json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openrouter import ChatOpenRouter

import config

_SYSTEM = """\
You are an intelligent job search assistant for Prowl, an AI-powered job scraping tool.
Answer the user's questions using the live data snapshot provided below. Be specific — use actual numbers.

When a chart would genuinely help (distributions, comparisons, trends), include an ECharts option object.
Chart styling (always dark-UI friendly):
  - backgroundColor: "transparent"
  - textStyle / axisLabel color: "#94a6b8"
  - title textStyle color: "#e2e8f0"
  - splitLine / axisLine color: "#1e293b" / "#334155"
  - Accent palette: violet #8b5cf6, emerald #34d399, amber #fbbf24, sky #38bdf8, rose #f43f5e, slate #64748b

RESPOND ONLY with valid JSON — no markdown fences, no extra text:
{
  "text": "<your answer, markdown ok, 2-5 sentences>",
  "chart": <complete ECharts option object, or null>
}

LIVE DATA SNAPSHOT:
{data}
"""


class InsightsChat:
    def __init__(self):
        self._llm = ChatOpenRouter(
            model=config.INSIGHTS_MODEL,
            openrouter_api_key=config.OPENROUTER_API_KEY,
            temperature=0.3,
        )

    async def ask(self, message: str, data: dict, history: list[dict]) -> dict:
        system = _SYSTEM.replace("{data}", json.dumps(data, indent=2))

        msgs: list = [SystemMessage(content=system)]
        for h in history[-8:]:
            cls = HumanMessage if h["role"] == "user" else AIMessage
            msgs.append(cls(content=h["content"]))
        msgs.append(HumanMessage(content=message))

        response = await self._llm.ainvoke(msgs)
        raw = response.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            return json.loads(raw.strip())
        except Exception:
            return {"text": raw, "chart": None}
