import pytest

from app.orders import broken_average, accumulate


def test_broken_average_single_value():
    with pytest.raises(ZeroDivisionError):
        broken_average([1.0])


def test_accumulate_should_not_leak_state():
    first = accumulate([1, 2])
    second = accumulate([3])
    assert first == [1, 2]
    assert second == [3]
