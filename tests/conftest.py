# conftest.py
"""Pytest configuration and shared fixtures."""

from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_boto_session():
    """Mock boto3 session for all tests."""
    with patch("boto3.Session") as mock_session_class:
        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Default successful token generation
        mock_client.generate_db_auth_token.return_value = "test-token"

        yield {
            "session_class": mock_session_class,
            "session": mock_session,
            "client": mock_client,
        }


@pytest.fixture
def sample_rds_url():
    """Sample RDS connection URL."""
    # Backwards compatibility for SQLAlchemy 1.4/2.0
    try:
        from sqlalchemy import URL
    except ImportError:
        from sqlalchemy.engine.url import URL

    return URL.create(
        drivername="mysql+pymysql",
        username="testuser",
        host="mydb.us-east-1.rds.amazonaws.com",
        port=3306,
        database="testdb",
        query={"use_iam_auth": "true"},
    )


# pytest.ini
"""
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --cov=sqlalchemy_rds_iam
    --cov-report=html
    --cov-report=term-missing
    --strict-markers
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    unit: marks tests as unit tests
"""

# tox.ini
"""
[tox]
envlist = py{38,39,310,311,312}, lint, docs
isolated_build = True

[testenv]
deps =
    pytest>=7.0
    pytest-cov>=4.0
    pytest-mock>=3.0
    moto[rds]>=4.0  # For AWS mocking
extras = dev
commands =
    pytest {posargs}

[testenv:lint]
deps =
    black>=23.0
    flake8>=6.0
    mypy>=1.0
    isort>=5.0
commands =
    black --check src tests
    flake8 src tests
    mypy src
    isort --check-only src tests

[testenv:docs]
deps =
    sphinx>=5.0
    sphinx-rtd-theme>=1.0
extras = docs
commands =
    sphinx-build -b html docs docs/_build/html
"""

# .github/workflows/tests.yml
"""
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']
        sqlalchemy-version: ['1.4.*', '2.0.*']

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install tox tox-gh-actions
        pip install sqlalchemy==${{ matrix.sqlalchemy-version }}

    - name: Test with tox
      run: tox

    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
      if: matrix.python-version == '3.11' && matrix.sqlalchemy-version == '2.0.*'
      with:
        file: ./coverage.xml
        fail_ci_if_error: true

  lint:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install tox

    - name: Run linting
      run: tox -e lint
"""
