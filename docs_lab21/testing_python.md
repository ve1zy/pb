# Тестирование на Python

## pytest
pip install pytest
pytest — запуск всех тестов.
pytest test_file.py — запуск конкретного файла.
pytest -v — подробный вывод.

## Структура теста
def test_addition():
    assert 1 + 1 == 2

def test_string():
    assert "hello".upper() == "HELLO"

## Fixtures
@pytest.fixture
def sample_data():
    return {"name": "Alice", "age": 30}

def test_user(sample_data):
    assert sample_data["name"] == "Alice"

## Параметризация
@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3),
    (5, 5, 10),
    (-1, 1, 0),
])
def test_add(a, b, expected):
    assert a + b == expected

## Mock
from unittest.mock import MagicMock
mock = MagicMock(return_value=42)
assert mock() == 42

## Coverage
pip install pytest-cov
pytest --cov=myproject --cov-report=html
Покрытие показывает процент протестированного кода.
