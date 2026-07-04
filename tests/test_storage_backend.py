"""
Tests for utils/storage_backend.py
"""
import json
from pathlib import Path
import pytest
from utils.storage_backend import (
    load_json_with_fallback,
    save_json_with_fallback,
    append_list_with_fallback,
    fetch_list_with_fallback,
)


@pytest.mark.unit
def test_load_json_with_fallback_redis_success(mock_redis, temp_file):
    # Given
    redis_key = "test_key"
    mock_redis.set(redis_key, json.dumps({"a": 1, "b": 2}))
    defaults = {"b": 3, "c": 4}

    # When
    result = load_json_with_fallback(
        redis_client=mock_redis,
        redis_key=redis_key,
        file_path=temp_file,
        defaults=defaults,
    )

    # Then
    assert result == {"a": 1, "b": 2, "c": 4}


@pytest.mark.unit
def test_load_json_with_fallback_file_success(temp_file):
    # Given
    data = {"x": 10, "y": 20}
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
    defaults = {"y": 30, "z": 40}

    # When
    result = load_json_with_fallback(
        redis_client=None,
        redis_key="test_key",
        file_path=temp_file,
        defaults=defaults,
    )

    # Then
    assert result == {"x": 10, "y": 20, "z": 40}


@pytest.mark.unit
def test_load_json_with_fallback_memory_defaults(temp_file):
    # Given
    defaults = {"y": 30, "z": 40}
    if temp_file.exists():
        temp_file.unlink()

    # When
    result = load_json_with_fallback(
        redis_client=None,
        redis_key="test_key",
        file_path=temp_file,
        defaults=defaults,
    )

    # Then
    assert result == defaults


@pytest.mark.unit
def test_save_json_with_fallback_redis(mock_redis, temp_file):
    # Given
    redis_key = "test_key"
    data = {"hello": "world"}

    # When
    success = save_json_with_fallback(
        data,
        redis_client=mock_redis,
        redis_key=redis_key,
        file_path=temp_file,
    )

    # Then
    assert success is True
    stored_redis = mock_redis.get(redis_key)
    assert stored_redis is not None
    assert json.loads(stored_redis) == data


@pytest.mark.unit
def test_save_json_with_fallback_file(temp_file):
    # Given
    data = {"hello": "file"}
    if temp_file.exists():
        temp_file.unlink()

    # When
    success = save_json_with_fallback(
        data,
        redis_client=None,
        redis_key="test_key",
        file_path=temp_file,
    )

    # Then
    assert success is True
    assert temp_file.exists()
    with open(temp_file, "r", encoding="utf-8") as f:
        stored_file = json.load(f)
    assert stored_file == data


@pytest.mark.unit
def test_append_and_fetch_list_redis(mock_redis, temp_file):
    # Given
    redis_key = "test_list"
    item1 = {"id": 1, "val": "a"}
    item2 = {"id": 2, "val": "b"}

    # When
    append_list_with_fallback(
        item1,
        redis_client=mock_redis,
        redis_list_key=redis_key,
        file_path=temp_file,
        max_entries=2,
    )
    append_list_with_fallback(
        item2,
        redis_client=mock_redis,
        redis_list_key=redis_key,
        file_path=temp_file,
        max_entries=2,
    )
    result = fetch_list_with_fallback(
        redis_client=mock_redis,
        redis_list_key=redis_key,
        file_path=temp_file,
    )

    # Then
    assert result == [item1, item2]


@pytest.mark.unit
def test_append_and_fetch_list_file(temp_file):
    # Given
    item1 = {"id": 1, "val": "a"}
    item2 = {"id": 2, "val": "b"}
    item3 = {"id": 3, "val": "c"}

    # When
    append_list_with_fallback(
        item1,
        redis_client=None,
        redis_list_key="test_list",
        file_path=temp_file,
        max_entries=2,
    )
    append_list_with_fallback(
        item2,
        redis_client=None,
        redis_list_key="test_list",
        file_path=temp_file,
        max_entries=2,
    )
    append_list_with_fallback(
        item3,
        redis_client=None,
        redis_list_key="test_list",
        file_path=temp_file,
        max_entries=2,
    )
    result = fetch_list_with_fallback(
        redis_client=None,
        redis_list_key="test_list",
        file_path=temp_file,
    )

    # Then
    assert result == [item2, item3]
