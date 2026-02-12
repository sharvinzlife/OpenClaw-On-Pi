"""News skill — fetch headlines from RSS feeds via feedparser."""

import feedparser

from src.skills.base_skill import BaseSkill, SkillResult

DEFAULT_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://feeds.reuters.com/reuters/topNews",
]


class NewsSkill(BaseSkill):
    """Fetch latest news headlines from RSS feeds."""

    name = "news"
    command = "news"
    description = "Get latest news headlines"
    permission_level = "guest"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        feeds = self.config.get("feeds", DEFAULT_FEEDS)
        max_headlines = self.config.get("max_headlines", 5)

        # Optional: user can specify a feed index or keyword filter
        keyword = " ".join(args).strip().lower() if args else ""

        headlines: list[dict] = []

        for feed_url in feeds:
            try:
                parsed = feedparser.parse(feed_url)
                source = parsed.feed.get("title", feed_url)

                for entry in parsed.entries[:max_headlines * 2]:
                    title = entry.get("title", "").strip()
                    link = entry.get("link", "")
                    published = entry.get("published", "")

                    if not title:
                        continue

                    if keyword and keyword not in title.lower():
                        continue

                    headlines.append({
                        "source": source,
                        "title": title,
                        "link": link,
                        "published": published,
                    })
            except Exception:
                continue

        if not headlines:
            if keyword:
                return SkillResult(error=f"No headlines found matching: {keyword}")
            return SkillResult(error="Failed to fetch news from any feed")

        # Deduplicate by title and limit
        seen = set()
        unique = []
        for h in headlines:
            if h["title"] not in seen:
                seen.add(h["title"])
                unique.append(h)
        headlines = unique[:max_headlines]

        lines = ["📰 Latest Headlines", ""]
        for i, h in enumerate(headlines, 1):
            lines.append(f"{i}. {h['title']}")
            if h["link"]:
                lines.append(f"   🔗 {h['link']}")
            lines.append(f"   📡 {h['source']}")
            lines.append("")

        return SkillResult(text="\n".join(lines).strip())

    @classmethod
    def check_dependencies(cls) -> bool:
        try:
            import feedparser  # noqa: F811
            return True
        except ImportError:
            return False
