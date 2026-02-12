"""Unit tests for MessageRecord and DashboardState message feed.

Tests Task 7.1: MessageRecord dataclass and message feed with 100-record cap.
Requirements: 5.1, 5.6
"""

from src.web.dashboard import DashboardState, MessageRecord


class TestMessageRecord:
    def test_dataclass_fields(self):
        record = MessageRecord(
            username="alice",
            user_message="hello",
            bot_response="hi there",
            timestamp="2024-01-01T00:00:00",
        )
        assert record.username == "alice"
        assert record.user_message == "hello"
        assert record.bot_response == "hi there"
        assert record.timestamp == "2024-01-01T00:00:00"


class TestMessageFeed:
    def test_initial_feed_is_empty(self):
        state = DashboardState()
        assert state.message_feed == []

    def test_add_single_record(self):
        state = DashboardState()
        state.add_message_record("bob", "what's up", "not much")
        assert len(state.message_feed) == 1
        rec = state.message_feed[0]
        assert rec.username == "bob"
        assert rec.user_message == "what's up"
        assert rec.bot_response == "not much"
        assert rec.timestamp  # non-empty ISO string

    def test_records_have_iso_timestamp(self):
        state = DashboardState()
        state.add_message_record("user1", "msg", "resp")
        ts = state.message_feed[0].timestamp
        # ISO format contains 'T' separator
        assert "T" in ts

    def test_cap_at_100_records(self):
        state = DashboardState()
        for i in range(110):
            state.add_message_record(f"user{i}", f"msg{i}", f"resp{i}")
        assert len(state.message_feed) == 100

    def test_cap_keeps_most_recent(self):
        state = DashboardState()
        for i in range(105):
            state.add_message_record(f"user{i}", f"msg{i}", f"resp{i}")
        # Oldest should be user5 (indices 5-104 survive)
        assert state.message_feed[0].username == "user5"
        assert state.message_feed[-1].username == "user104"
