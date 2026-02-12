"""Wiki skill — fetch Wikipedia summaries via the REST API."""

import httpx

import importlib.util

from src.skills.base_skill import BaseSkill, SkillResult


class WikiSkill(BaseSkill):
    """Fetch Wikipedia article summaries."""

    name = "wiki"
    command = "wiki"
    description = "Look up Wikipedia summaries"
    permission_level = "guest"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        query = " ".join(args).strip()
        if not query:
            return SkillResult(error="Usage: /wiki <topic>\nExample: /wiki Raspberry Pi")

        lang = self.config.get("language", "en")
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{query}"

        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "OpenClaw-Bot"})
                resp.raise_for_status()
                data = resp.json()

            title = data.get("title", query)
            extract = data.get("extract", "")
            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            doc_type = data.get("type", "")

            if doc_type == "disambiguation":
                return SkillResult(
                    text=f"📚 '{title}' is a disambiguation page.\nTry being more specific."
                )

            if not extract:
                return SkillResult(error=f"No summary found for: {query}")

            # Truncate long summaries for Telegram readability
            if len(extract) > 1000:
                extract = extract[:997] + "..."

            lines = [f"📖 {title}", "", extract]
            if page_url:
                lines.append(f"\n🔗 {page_url}")

            return SkillResult(text="\n".join(lines))

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return SkillResult(error=f"No Wikipedia article found for: {query}")
            return SkillResult(error=f"Wikipedia API error: {e.response.status_code}")
        except Exception as e:
            return SkillResult(error=f"Failed to fetch Wikipedia summary: {e}")

    @classmethod
    def check_dependencies(cls) -> bool:
        return importlib.util.find_spec("httpx") is not None
