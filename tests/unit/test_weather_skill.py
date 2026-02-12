"""Unit tests for WeatherSkill error handling and robustness."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.skills.weather import WeatherSkill


@pytest.fixture
def skill():
    return WeatherSkill(config={"enabled": True})


# Sample valid wttr.in JSON response for mocking
VALID_WEATHER_RESPONSE = {
    "current_condition": [
        {
            "temp_C": "18",
            "FeelsLikeC": "16",
            "weatherDesc": [{"value": "Partly cloudy"}],
            "humidity": "65",
            "windspeedKmph": "12",
            "winddir16Point": "NW",
            "precipMM": "0.0",
        }
    ],
    "nearest_area": [
        {
            "areaName": [{"value": "London"}],
            "country": [{"value": "United Kingdom"}],
        }
    ],
}


class TestWeatherSkillExecute:
    """Tests for WeatherSkill.execute()."""

    @pytest.mark.asyncio
    async def test_no_location_returns_usage(self, skill):
        result = await skill.execute(user_id=1, args=[])
        assert result.error is not None
        assert "Usage" in result.error

    @pytest.mark.asyncio
    async def test_class_attributes(self):
        assert WeatherSkill.name == "weather"
        assert WeatherSkill.command == "weather"
        assert WeatherSkill.permission_level == "guest"

    @pytest.mark.asyncio
    async def test_check_dependencies(self):
        assert WeatherSkill.check_dependencies() is True

    @pytest.mark.asyncio
    async def test_timeout_returns_temporarily_unavailable(self, skill):
        """Timeout errors should return 'Weather service temporarily unavailable'."""
        with patch("src.skills.weather.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await skill.execute(user_id=1, args=["London"])
            assert result.error == "Weather service temporarily unavailable"

    @pytest.mark.asyncio
    async def test_http_error_includes_status_code(self, skill):
        """HTTP errors should include the status code in the message."""
        with patch("src.skills.weather.httpx.AsyncClient") as mock_client_cls:
            mock_response = httpx.Response(
                status_code=500,
                request=httpx.Request("GET", "https://wttr.in/London?format=j1"),
            )
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await skill.execute(user_id=1, args=["London"])
            assert result.error is not None
            assert "500" in result.error

    @pytest.mark.asyncio
    async def test_http_404_returns_location_not_found(self, skill):
        """404 errors should return 'Location not found'."""
        with patch("src.skills.weather.httpx.AsyncClient") as mock_client_cls:
            mock_response = httpx.Response(
                status_code=404,
                request=httpx.Request("GET", "https://wttr.in/Xyzzy?format=j1"),
            )
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await skill.execute(user_id=1, args=["Xyzzy"])
            assert result.error is not None
            assert "Location not found" in result.error

    @pytest.mark.asyncio
    async def test_connect_error_returns_network_message(self, skill):
        """Network connection errors should return a descriptive message."""
        with patch("src.skills.weather.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await skill.execute(user_id=1, args=["London"])
            assert result.error is not None
            assert "connect" in result.error.lower()

    @pytest.mark.asyncio
    async def test_successful_weather_response(self, skill):
        """Successful response should return formatted weather text."""
        import json

        with patch("src.skills.weather.httpx.AsyncClient") as mock_client_cls:
            mock_response = httpx.Response(
                status_code=200,
                request=httpx.Request("GET", "https://wttr.in/London?format=j1"),
                content=json.dumps(VALID_WEATHER_RESPONSE).encode(),
            )

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await skill.execute(user_id=1, args=["London"])
            assert result.error is None
            assert result.text is not None
            assert "London" in result.text
            assert "18°C" in result.text
            assert "Partly cloudy" in result.text
            assert "65%" in result.text
            assert "12 km/h" in result.text

    @pytest.mark.asyncio
    async def test_client_uses_15s_timeout_and_follow_redirects(self, skill):
        """Verify the httpx client is created with timeout=15 and follow_redirects=True."""
        with patch("src.skills.weather.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timed out")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await skill.execute(user_id=1, args=["London"])

            mock_client_cls.assert_called_once_with(
                timeout=15, follow_redirects=True
            )
