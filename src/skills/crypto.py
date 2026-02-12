"""Crypto skill — fetch cryptocurrency prices from CoinGecko (free, no API key)."""

import httpx

from src.skills.base_skill import BaseSkill, SkillResult

# Common aliases so users can type /crypto btc instead of /crypto bitcoin
ALIASES = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "ada": "cardano",
    "dot": "polkadot",
    "doge": "dogecoin",
    "xrp": "ripple",
    "bnb": "binancecoin",
    "matic": "matic-network",
    "avax": "avalanche-2",
    "link": "chainlink",
    "ltc": "litecoin",
    "atom": "cosmos",
    "uni": "uniswap",
    "shib": "shiba-inu",
}


class CryptoSkill(BaseSkill):
    """Fetch cryptocurrency prices from CoinGecko."""

    name = "crypto"
    command = "crypto"
    description = "Get cryptocurrency prices"
    permission_level = "guest"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        query = " ".join(args).strip().lower()
        if not query:
            return SkillResult(
                error="Usage: /crypto <coin>\nExample: /crypto bitcoin\nAliases: btc, eth, sol, doge, xrp"
            )

        coin_id = ALIASES.get(query, query)
        api_base = self.config.get("api_base_url", "https://api.coingecko.com/api/v3")
        url = f"{api_base}/coins/{coin_id}"
        params = {
            "localization": "false",
            "tickers": "false",
            "community_data": "false",
            "developer_data": "false",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params, headers={"User-Agent": "OpenClaw-Bot"})
                resp.raise_for_status()
                data = resp.json()

            name = data.get("name", coin_id)
            symbol = data.get("symbol", "?").upper()
            market = data.get("market_data", {})

            price_usd = market.get("current_price", {}).get("usd")
            change_24h = market.get("price_change_percentage_24h")
            high_24h = market.get("high_24h", {}).get("usd")
            low_24h = market.get("low_24h", {}).get("usd")
            mcap = market.get("market_cap", {}).get("usd")
            volume = market.get("total_volume", {}).get("usd")

            arrow = "📈" if (change_24h or 0) >= 0 else "📉"

            lines = [f"🪙 {name} ({symbol})"]

            if price_usd is not None:
                lines.append(f"💰 Price: ${price_usd:,.2f}")
            if change_24h is not None:
                lines.append(f"{arrow} 24h: {change_24h:+.2f}%")
            if high_24h is not None and low_24h is not None:
                lines.append(f"📊 24h Range: ${low_24h:,.2f} — ${high_24h:,.2f}")
            if mcap is not None:
                lines.append(f"🏦 Market Cap: ${mcap:,.0f}")
            if volume is not None:
                lines.append(f"📦 24h Volume: ${volume:,.0f}")

            return SkillResult(text="\n".join(lines))

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return SkillResult(error=f"Coin not found: {query}\nTry the full name (e.g. 'bitcoin') or common aliases (btc, eth, sol)")
            return SkillResult(error=f"CoinGecko API error: {e.response.status_code}")
        except Exception as e:
            return SkillResult(error=f"Failed to fetch crypto data: {e}")

    @classmethod
    def check_dependencies(cls) -> bool:
        try:
            import httpx  # noqa: F811
            return True
        except ImportError:
            return False
