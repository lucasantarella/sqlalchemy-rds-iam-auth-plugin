# test_performance.py
"""Performance tests for the plugin."""

import time
from unittest.mock import Mock, patch

import pytest

# Backwards compatibility for SQLAlchemy 1.4/2.0
try:
    from sqlalchemy import URL
except ImportError:
    from sqlalchemy.engine.url import URL

from sqlalchemy_rds_iam.plugin import RDSIAMAuthPlugin


@pytest.mark.slow
class TestPerformance:
    """Performance-related tests."""

    @patch("boto3.Session")
    def test_token_caching_performance(self, mock_session_class):
        """Test that token caching improves performance."""
        mock_client = Mock()
        mock_session = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Mock token generation with delay
        def slow_token_gen(*args, **kwargs):
            time.sleep(0.1)  # Simulate network latency
            return "performance-token"

        mock_client.generate_db_auth_token.side_effect = slow_token_gen

        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="mydb.us-east-1.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        plugin = RDSIAMAuthPlugin(url, {})

        # First call - should be slow
        start = time.time()
        token1 = plugin.get_authentication_token()
        first_call_time = time.time() - start

        # Subsequent calls - should be fast (cached)
        start = time.time()
        for _ in range(100):
            token = plugin.get_authentication_token()
            assert token == token1
        cached_calls_time = time.time() - start

        # Cached calls should be much faster
        assert cached_calls_time < first_call_time
        assert mock_client.generate_db_auth_token.call_count == 1
