"""Property-based tests for ContextStore.

Feature: openclaw-telegram-bot
Tests Properties 10, 15, 16, and 17 from the design document.
"""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from src.utils.context_store import ContextStore


# Strategies
user_id_strategy = st.integers(min_value=1, max_value=10**12)
message_role = st.sampled_from(["user", "assistant"])


@st.composite
def message_content(draw):
    """Generate valid message content."""
    return draw(st.text(
        min_size=1,
        max_size=500,
        alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S', 'Z'))
    ).filter(lambda x: x.strip()))


@st.composite
def message_list(draw, min_size=1, max_size=10):
    """Generate a list of messages."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    messages = []
    for _ in range(size):
        messages.append({
            "role": draw(message_role),
            "content": draw(message_content()),
        })
    return messages


class TestContextResetClearsHistory:
    """Property 10: Context Reset Clears History
    
    For any user with existing conversation context, calling 
    ContextStore.clear_context(user_id) SHALL result in get_context(user_id) 
    returning an empty list.
    
    **Validates: Requirements 5.5, 9.4**
    """
    
    @given(
        user_id=user_id_strategy,
        messages=message_list(min_size=1, max_size=10),
    )
    @settings(max_examples=100, deadline=None)
    def test_clear_context_returns_empty_list(self, user_id, messages):
        """Property 10: Clearing context results in empty list."""
        store = ContextStore(max_messages=20)
        
        # Add messages
        for msg in messages:
            store.add_message(user_id, msg["role"], msg["content"])
        
        # Verify messages exist
        assert len(store.get_context(user_id)) > 0
        
        # Clear context
        store.clear_context(user_id)
        
        # Verify empty
        assert store.get_context(user_id) == []
    
    @given(
        user_id=user_id_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_clear_nonexistent_context_safe(self, user_id):
        """Clearing non-existent context doesn't raise error."""
        store = ContextStore()
        
        # Should not raise
        store.clear_context(user_id)
        
        # Should return empty
        assert store.get_context(user_id) == []


class TestContextIsolationBetweenUsers:
    """Property 15: Context Isolation Between Users
    
    For any two distinct user IDs, messages added to one user's context 
    via ContextStore.add_message() SHALL NOT appear in the other user's 
    context returned by get_context().
    
    **Validates: Requirements 9.1**
    """
    
    @given(
        user_id1=user_id_strategy,
        user_id2=user_id_strategy,
        messages1=message_list(min_size=1, max_size=5),
        messages2=message_list(min_size=1, max_size=5),
    )
    @settings(max_examples=100, deadline=None)
    def test_messages_isolated_between_users(
        self, user_id1, user_id2, messages1, messages2
    ):
        """Property 15: Messages don't leak between users."""
        # Ensure different users
        if user_id1 == user_id2:
            user_id2 = user_id1 + 1
        
        store = ContextStore(max_messages=20)
        
        # Add messages for user1
        for msg in messages1:
            store.add_message(user_id1, msg["role"], msg["content"])
        
        # Add messages for user2
        for msg in messages2:
            store.add_message(user_id2, msg["role"], msg["content"])
        
        # Get contexts
        context1 = store.get_context(user_id1)
        context2 = store.get_context(user_id2)
        
        # Verify isolation
        assert len(context1) == len(messages1)
        assert len(context2) == len(messages2)
        
        # Verify content matches
        for i, msg in enumerate(messages1):
            assert context1[i]["content"] == msg["content"]
        
        for i, msg in enumerate(messages2):
            assert context2[i]["content"] == msg["content"]
        
        # Verify no cross-contamination
        contents1 = {m["content"] for m in context1}
        contents2 = {m["content"] for m in context2}
        
        # Messages should only appear in their respective contexts
        for msg in messages1:
            assert msg["content"] in contents1
        
        for msg in messages2:
            assert msg["content"] in contents2


class TestContextTruncationOnLimit:
    """Property 16: Context Truncation on Limit
    
    For any user context that exceeds max_messages or max_tokens after 
    adding a message, the ContextStore SHALL truncate older messages such 
    that the resulting context is within limits while preserving the most 
    recent messages.
    
    **Validates: Requirements 9.3**
    """
    
    @given(
        user_id=user_id_strategy,
        max_messages=st.integers(min_value=2, max_value=10),
        num_messages=st.integers(min_value=5, max_value=20),
    )
    @settings(max_examples=100, deadline=None)
    def test_truncation_respects_max_messages(
        self, user_id, max_messages, num_messages
    ):
        """Property 16: Context truncated to max_messages."""
        store = ContextStore(max_messages=max_messages)
        
        # Add more messages than limit
        messages = []
        for i in range(num_messages):
            content = f"message_{i}"
            store.add_message(user_id, "user", content)
            messages.append(content)
        
        context = store.get_context(user_id)
        
        # Should not exceed limit
        assert len(context) <= max_messages
        
        # Should contain most recent messages
        expected_messages = messages[-max_messages:]
        actual_contents = [m["content"] for m in context]
        
        assert actual_contents == expected_messages
    
    @given(
        user_id=user_id_strategy,
        max_messages=st.integers(min_value=3, max_value=10),
    )
    @settings(max_examples=50, deadline=None)
    def test_most_recent_messages_preserved(self, user_id, max_messages):
        """Most recent messages are preserved after truncation."""
        store = ContextStore(max_messages=max_messages)
        
        # Add exactly max_messages + 2
        for i in range(max_messages + 2):
            store.add_message(user_id, "user", f"msg_{i}")
        
        context = store.get_context(user_id)
        
        # Last message should be the most recent
        assert context[-1]["content"] == f"msg_{max_messages + 1}"
        
        # First message should be msg_2 (oldest two were truncated)
        assert context[0]["content"] == "msg_2"


class TestContextPersistenceRoundTrip:
    """Property 17: Context Persistence Round-Trip
    
    For any set of user contexts stored in ContextStore, calling 
    save_to_disk() followed by load_from_disk() on a new ContextStore 
    instance SHALL restore equivalent context data for all users.
    
    **Validates: Requirements 9.5**
    """
    
    @given(
        user_ids=st.lists(user_id_strategy, min_size=1, max_size=5, unique=True),
        messages_per_user=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=50, deadline=None)
    def test_save_load_round_trip(self, user_ids, messages_per_user):
        """Property 17: Contexts survive save/load cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "contexts.json"
            
            # Create store and add messages
            store1 = ContextStore(str(storage_path), max_messages=20)
            
            expected_contexts = {}
            for user_id in user_ids:
                expected_contexts[user_id] = []
                for i in range(messages_per_user):
                    content = f"user_{user_id}_msg_{i}"
                    role = "user" if i % 2 == 0 else "assistant"
                    store1.add_message(user_id, role, content)
                    expected_contexts[user_id].append({"role": role, "content": content})
            
            # Save to disk
            store1.save_to_disk()
            
            # Create new store and load
            store2 = ContextStore(str(storage_path), max_messages=20)
            store2.load_from_disk()
            
            # Verify all contexts restored
            for user_id in user_ids:
                loaded_context = store2.get_context(user_id)
                expected = expected_contexts[user_id]
                
                assert len(loaded_context) == len(expected), (
                    f"User {user_id}: expected {len(expected)} messages, got {len(loaded_context)}"
                )
                
                for i, (loaded, exp) in enumerate(zip(loaded_context, expected)):
                    assert loaded["role"] == exp["role"]
                    assert loaded["content"] == exp["content"]
    
    @given(
        user_id=user_id_strategy,
    )
    @settings(max_examples=30, deadline=None)
    def test_load_from_nonexistent_file_safe(self, user_id):
        """Loading from non-existent file doesn't crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "nonexistent.json"
            
            store = ContextStore(str(storage_path))
            
            # Should not raise
            store.load_from_disk()
            
            # Should have empty contexts
            assert store.get_context(user_id) == []
