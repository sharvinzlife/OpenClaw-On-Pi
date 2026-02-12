"""Weather skill — fetch weather info from wttr.in (no API key needed)."""

import httpx

import importlib.util

from src.skills.base_skill import BaseSkill, SkillResult



class WeatherSkill(BaseSkill):
    """Fetch current weather for a location via wttr.in."""

    name = "weather"
    command = "weather"
    description = "Get current weather for a location"
    permission_level = "guest"

    async def execute(self, user_id: int, args: list[str], **kwargs) -> SkillResult:
        location = " ".join(args).strip()
        if not location:
            return SkillResult(error="Usage: /weather <city>\nExample: /weather London")

        api_url = self.config.get("api_base_url", "https://wttr.in")
        url = f"{api_url}/{location}?format=j1"

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "OpenClaw-Bot"})
                resp.raise_for_status()
                data = resp.json()

            current = data.get("current_condition", [{}])[0]
            area = data.get("nearest_area", [{}])[0]

            city = area.get("areaName", [{}])[0].get("value", location)
            country = area.get("country", [{}])[0].get("value", "")
            temp_c = current.get("temp_C", "?")
            feels = current.get("FeelsLikeC", "?")
            desc = current.get("weatherDesc", [{}])[0].get("value", "?")
            humidity = current.get("humidity", "?")
            wind_kmph = current.get("windspeedKmph", "?")
            wind_dir = current.get("winddir16Point", "")
            precip = current.get("precipMM", "0")

            lines = [
                f"🌍 {city}, {country}",
                f"🌡️ {temp_c}°C (feels like {feels}°C)",
                f"☁️ {desc}",
                f"💧 Humidity: {humidity}%",
                f"💨 Wind: {wind_kmph} km/h {wind_dir}",
                f"🌧️ Precipitation: {precip} mm",
            ]
            return SkillResult(text="\n".join(lines))

        except httpx.TimeoutException:
            return SkillResult(error="Weather service temporarily unavailable")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return SkillResult(error=f"Location not found: {location}")
            return SkillResult(error=f"Weather API error (HTTP {e.response.status_code})")
        except httpx.ConnectError:
            return SkillResult(
                error="Unable to connect to weather service — check network connection"
            )
        except httpx.RequestError as e:
            return SkillResult(error=f"Weather request failed: {e}")
        except Exception as e:
            return SkillResult(error=f"Failed to fetch weather: {e}")

    @classmethod
    def check_dependencies(cls) -> bool:
        return importlib.util.find_spec("httpx") is not None
