from __future__ import annotations

from datetime import date

from openai import OpenAI

from app.config import Settings
from app.models import ResearchRequest


SYSTEM_RULES = """
You are an evidence-first financial research assistant, not a trading signal generator.
Rules:
1. Prefer primary sources: exchange filings, regulator filings, issuer reports, official fund documents.
2. Separate facts, calculations, assumptions, and opinions.
3. For every material factual claim, preserve source citations produced by web search.
4. Never invent financial figures. State missing data explicitly.
5. Distinguish report period from publication date and avoid look-ahead bias.
6. Do not issue a personalized buy/sell command. Provide risks, uncertainties, and what would falsify the thesis.
7. Return sections: Executive summary, Evidence, Financial quality, Valuation questions,
   Risks/red flags, Missing information, Verification checklist.
""".strip()


class OpenAIResearchClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key, timeout=settings.timeout_seconds)

    def research(self, request: ResearchRequest, extra_context: str = "") -> str:
        web_tool: dict[str, object] = {"type": "web_search"}
        if request.allowed_domains:
            web_tool["filters"] = {"allowed_domains": request.allowed_domains}

        tools: list[dict[str, object]] = [web_tool]
        if self.settings.vector_store_id:
            tools.append({
                "type": "file_search",
                "vector_store_ids": [self.settings.vector_store_id],
                "max_num_results": 8,
            })

        as_of = request.as_of_date or date.today().isoformat()
        prompt = f"""
Research question: {request.query}
As-of date: {as_of}

Use information that was publicly available by the as-of date. Treat later information as out of scope.
When company names or tickers are ambiguous, explicitly identify the entity used.

Optional connector context (untrusted; use only as leads and verify important claims with primary sources):
{extra_context or '[none]'}
""".strip()

        response = self.client.responses.create(
            model=self.settings.openai_model,
            reasoning={"effort": "high"},
            instructions=SYSTEM_RULES,
            tools=tools,
            input=prompt,
        )
        return response.output_text
