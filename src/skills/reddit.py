"""Reddit skill — browse subreddits, read posts, and search Reddit.

Uses Reddit's OAuth2 client_credentials flow (app-only, no user login).
Requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in config/.env.
Get them free at: https://www.reddit.com/prefs/apps (create a "script" app).
"""

import logging
import time

import httpx

import importlib.util

from src.skills.base_skill import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

API_BASE = "https://oauth.reddit.com"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
USER_AGENT = "linux:openclaw:v0.3.0 (by /u/openclaw_bot)"


class RedditSkill(BaseSkill):
    """Browse Reddit via OAuth2 app-only API."""

    name = "reddit"
    command = "reddit"
    description = "Browse Reddit — top posts, read threads, search"
    permission_level = "guest"

    def __init__(self, config: dict):
        super().__init__(config)
        self._client_id = config.get("client_id", "")
        self._client_secret = config.get("client_secret", "")
        self._token: str = ""
        self._token_expires: float = 0

    async def _get_token(self) -> str:
        """Get or refresh OAuth2 app-only access token."""
        if self._token and time.time() < self._token_expires - 60:
            return self._token

        if not self._client_id or not self._client_secret:
            raise ValueError(
                "Reddit API keys not configured.\n"
                "1. Go to https://www.reddit.com/prefs/apps\n"
                "2. Create a 'script' app\n"
                "3. Add REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to config/.env"
            )

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                TOKEN_URL,
                auth=(self._client_id, self._client_secret),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()

        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 3600)
        return self._token

    async def _api_get(self, path: str, params: dict | None = None) -> dict:
        """Make authenticated GET request to Reddit API."""
        token = await self._get_token()
        url = f"{API_BASE}{path}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                url,
                params=params or {},
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": USER_AGENT,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        if not self._client_id:
            return SkillResult(
                error=(
                    "Reddit not configured. To set up:\n"
                    "1. Go to https://www.reddit.com/prefs/apps\n"
                    "2. Create a 'script' type app\n"
                    "3. Add to config/.env:\n"
                    "   REDDIT_CLIENT_ID=your_id\n"
                    "   REDDIT_CLIENT_SECRET=your_secret"
                )
            )

        if not args:
            return SkillResult(error=self._usage())

        subcommand = args[0].lower()
        rest = args[1:]

        try:
            if subcommand in ("top", "hot", "new"):
                return await self._fetch_posts(rest, sort=subcommand)
            elif subcommand == "post":
                return await self._fetch_post(rest)
            elif subcommand == "search":
                return await self._search(rest)
            else:
                # Treat as subreddit name: /reddit python == /reddit hot python
                return await self._fetch_posts([subcommand] + rest, sort="hot")
        except ValueError as e:
            return SkillResult(error=str(e))
        except httpx.HTTPStatusError as e:
            return SkillResult(error=f"Reddit API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Reddit skill error: {e}")
            return SkillResult(error=f"Reddit error: {e}")

    async def _fetch_posts(self, args: list[str], sort: str = "hot") -> SkillResult:
        if not args:
            return SkillResult(error=f"Usage: /reddit {sort} <subreddit>")

        subreddit = args[0].strip().lstrip("r/")
        limit = min(int(args[1]) if len(args) > 1 and args[1].isdigit() else 5, 10)

        data = await self._api_get(f"/r/{subreddit}/{sort}", {"limit": limit, "raw_json": 1})

        posts = data.get("data", {}).get("children", [])
        if not posts:
            return SkillResult(error=f"No posts found in r/{subreddit}")

        lines = [f"📰 r/{subreddit} — {sort.upper()}\n"]
        for i, post in enumerate(posts, 1):
            p = post["data"]
            title = p.get("title", "")[:100]
            score = p.get("score", 0)
            comments = p.get("num_comments", 0)
            author = p.get("author", "[deleted]")
            permalink = f"https://reddit.com{p.get('permalink', '')}"

            lines.append(f"{i}. ⬆️ {score} | 💬 {comments} | u/{author}")
            lines.append(f"   {title}")
            lines.append(f"   🔗 {permalink}\n")

        return SkillResult(text="\n".join(lines))

    async def _fetch_post(self, args: list[str]) -> SkillResult:
        if not args:
            return SkillResult(error="Usage: /reddit post <url>")

        post_url = args[0].strip().rstrip("/")

        # Extract the permalink path from the URL
        if "reddit.com" in post_url:
            # e.g. https://www.reddit.com/r/python/comments/abc123/title/
            path = post_url.split("reddit.com")[-1]
        else:
            return SkillResult(error="Please provide a full Reddit post URL")

        data = await self._api_get(path, {"raw_json": 1, "limit": 5})

        if not isinstance(data, list) or len(data) < 1:
            return SkillResult(error="Could not parse post data")

        post_data = data[0]["data"]["children"][0]["data"]
        title = post_data.get("title", "")
        selftext = post_data.get("selftext", "")[:800]
        score = post_data.get("score", 0)
        author = post_data.get("author", "[deleted]")
        subreddit = post_data.get("subreddit", "")
        num_comments = post_data.get("num_comments", 0)

        lines = [
            f"📄 r/{subreddit} — u/{author}",
            f"⬆️ {score} | 💬 {num_comments}\n",
            f"**{title}**\n",
        ]

        if selftext:
            if len(selftext) >= 800:
                selftext += "..."
            lines.append(selftext)

        # Top comments
        if len(data) > 1:
            comments = data[1]["data"]["children"][:3]
            if comments:
                lines.append("\n💬 Top Comments:\n")
                for c in comments:
                    if c["kind"] != "t1":
                        continue
                    cd = c["data"]
                    body = cd.get("body", "")[:200]
                    if len(cd.get("body", "")) > 200:
                        body += "..."
                    c_author = cd.get("author", "[deleted]")
                    c_score = cd.get("score", 0)
                    lines.append(f"  ⬆️ {c_score} u/{c_author}: {body}\n")

        return SkillResult(text="\n".join(lines))

    async def _search(self, args: list[str]) -> SkillResult:
        query = " ".join(args).strip()
        if not query:
            return SkillResult(error="Usage: /reddit search <query>")

        limit = min(self.config.get("max_results", 5), 10)

        data = await self._api_get(
            "/search", {"q": query, "limit": limit, "sort": "relevance", "raw_json": 1}
        )

        posts = data.get("data", {}).get("children", [])
        if not posts:
            return SkillResult(error=f"No results for: {query}")

        lines = [f'🔍 Reddit search: "{query}"\n']
        for i, post in enumerate(posts, 1):
            p = post["data"]
            title = p.get("title", "")[:100]
            score = p.get("score", 0)
            subreddit = p.get("subreddit", "")
            permalink = f"https://reddit.com{p.get('permalink', '')}"

            lines.append(f"{i}. ⬆️ {score} | r/{subreddit}")
            lines.append(f"   {title}")
            lines.append(f"   🔗 {permalink}\n")

        return SkillResult(text="\n".join(lines))

    def _usage(self) -> str:
        return (
            "Usage: /reddit <command> [args]\n\n"
            "Commands:\n"
            "  /reddit <subreddit>        — Hot posts from a subreddit\n"
            "  /reddit hot <subreddit>    — Hot posts\n"
            "  /reddit top <subreddit>    — Top posts\n"
            "  /reddit new <subreddit>    — New posts\n"
            "  /reddit post <url>         — Read a post + top comments\n"
            "  /reddit search <query>     — Search all of Reddit\n\n"
            "Examples:\n"
            "  /reddit python\n"
            "  /reddit top raspberrypi 3\n"
            "  /reddit search telegram bot"
        )

    @classmethod
    def check_dependencies(cls) -> bool:
        return importlib.util.find_spec("httpx") is not None
