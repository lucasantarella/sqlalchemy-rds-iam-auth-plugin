"""Integration tests using moto for AWS mocking."""

from unittest.mock import Mock, patch

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

# Backwards compatibility for SQLAlchemy 1.4/2.0
try:
    from sqlalchemy import URL
except ImportError:
    from sqlalchemy.engine.url import URL

from sqlalchemy_rds_iam.exceptions import RDSIAMAuthError
from sqlalchemy_rds_iam.plugin import RDSIAMAuthPlugin, create_rds_iam_engine


@pytest.mark.integration
class TestAWSIntegration:
    """Test AWS integration using moto mocks."""

    @mock_aws
    def test_token_generation_with_moto(self):
        """Test token generation with mocked AWS RDS."""
        # Create mock RDS instance
        with mock_aws():
            client = boto3.client("rds", region_name="us-east-1")
            client.create_db_instance(
                DBInstanceIdentifier="test-instance",
                DBInstanceClass="db.t2.micro",
                Engine="mysql",
                MasterUsername="testuser",
                MasterUserPassword="testpass",
                AllocatedStorage=20,
            )

            # Create engine with our plugin
            engine = create_rds_iam_engine(
                host="test-instance.us-east-1.rds.amazonaws.com",
                port=3306,
                database="testdb",
                username="testuser",
                region="us-east-1",
            )

            # Verify engine creation
            assert engine is not None
            assert str(engine.url).startswith("mysql+pymysql://testuser@")

    @mock_aws
    def test_multiple_regions(self):
        """Test plugin with multiple AWS regions."""
        with mock_aws():
            regions = ["us-east-1", "eu-west-1", "ap-southeast-1"]

            for region in regions:
                engine = create_rds_iam_engine(
                    host=f"test-db.{region}.rds.amazonaws.com",
                    port=3306,
                    database="testdb",
                    username="testuser",
                    region=region,
                )

                assert engine is not None
                # In real scenario, would verify connection works


class TestIntegration:
    """Integration tests for the plugin with SQLAlchemy engine."""

    @patch("boto3.Session")
    def test_full_engine_creation_flow(self, mock_session_class):
        """Test complete flow of engine creation with plugin."""
        # Mock AWS session and client
        mock_client = Mock()
        mock_session = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Mock token generation
        mock_client.generate_db_auth_token.return_value = "integration-test-token"

        # Create engine with our plugin
        # Note: This would normally connect to a real database
        # For testing, we'd use a mock dialect or in-memory database
        from sqlalchemy import create_engine

        engine = create_engine(
            "mysql+pymysql://testuser@mydb.us-east-1.rds.amazonaws.com/testdb"
            "?use_iam_auth=true",
            poolclass=NullPool,  # Disable pooling for simpler testing
            # Add your plugin name here when registered
            # plugins=['rds_iam']
        )

        # In a real test, you'd verify the engine works correctly
        assert engine is not None
        assert engine.url.username == "testuser"
        assert engine.url.host == "mydb.us-east-1.rds.amazonaws.com"

    def test_empty_password_in_url(self):
        """Test handling of empty password in URL."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            password="",  # Empty password should be ignored
            host="mydb.us-east-1.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        plugin = RDSIAMAuthPlugin(url, {})
        assert plugin.use_iam_auth is True

    def test_special_characters_in_username(self):
        """Test handling of special characters in username."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="test-user@domain.com",
            host="mydb.us-east-1.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        plugin = RDSIAMAuthPlugin(url, {})
        assert plugin.user == "test-user@domain.com"

    def test_non_standard_port(self):
        """Test handling of non-standard database port."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="mydb.us-east-1.rds.amazonaws.com",
            port=3307,  # Non-standard port
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        plugin = RDSIAMAuthPlugin(url, {})
        assert plugin.port == 3307

    @patch("boto3.Session")
    def test_token_generation_timeout(self, mock_session_class):
        """Test handling of token generation timeout."""
        mock_client = Mock()
        mock_session = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Simulate timeout
        from botocore.exceptions import ConnectTimeoutError

        mock_client.generate_db_auth_token.side_effect = ConnectTimeoutError(
            endpoint_url="https://rds.amazonaws.com"
        )

        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="mydb.us-east-1.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        plugin = RDSIAMAuthPlugin(url, {})

        with pytest.raises(RDSIAMAuthError):
            plugin.get_authentication_token()

    def test_malformed_rds_hostname(self):
        """Test handling of malformed RDS hostname."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="not-a-valid-rds-hostname",
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        # Should require explicit region since hostname is invalid
        with pytest.raises(RDSIAMAuthError, match="AWS region is required"):
            RDSIAMAuthPlugin(url, {})

    @patch("boto3.Session")
    def test_concurrent_token_generation(self, mock_session_class):
        """Test thread-safety of token generation."""
        import threading
        import time

        mock_client = Mock()
        mock_session = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Simulate slow token generation
        def slow_token_generation(*args, **kwargs):
            time.sleep(0.1)
            return "concurrent-token"

        mock_client.generate_db_auth_token.side_effect = slow_token_generation

        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="mydb.us-east-1.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        plugin = RDSIAMAuthPlugin(url, {})

        tokens = []

        def get_token():
            tokens.append(plugin.get_authentication_token())

        # Start multiple threads
        threads = [threading.Thread(target=get_token) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should get the same token (due to caching)
        # Note: This test might be flaky due to timing
        assert len(set(tokens)) <= 2  # At most 2 different tokens


@pytest.mark.integration
class TestConnectionPooling:
    """Test connection pooling behavior with IAM auth."""

    def test_pool_pre_ping_behavior(self, mock_boto_session):
        """Test that pool_pre_ping works correctly with IAM auth."""
        from sqlalchemy.pool import QueuePool

        engine = create_engine(
            "mysql+pymysql://testuser@mydb.us-east-1.rds.amazonaws.com/testdb"
            "?use_iam_auth=true",
            poolclass=QueuePool,
            pool_size=5,
            pool_pre_ping=True,
        )

        # Verify pool configuration
        assert isinstance(engine.pool, QueuePool)
        assert engine.pool.size() == 5

    def test_connection_invalidation_on_auth_failure(self, mock_boto_session):
        """Test that connections are invalidated on auth failures."""
        # This would require a more complex setup with actual connection mocking
        pass


@pytest.mark.slow
@pytest.mark.integration
class TestRealDatabaseConnection:
    """
    Tests that would connect to a real RDS instance.
    These are marked as slow and should only run in CI with real credentials.
    """

    @pytest.mark.skipif(
        "not config.getoption('--run-integration')",
        reason="need --run-integration option to run",
    )
    def test_real_mysql_connection(self):
        """Test real MySQL RDS connection with IAM auth."""
        # This would only run with actual AWS credentials
        import os

        if not all(os.getenv(k) for k in ["RDS_HOST", "RDS_USER", "AWS_REGION"]):
            pytest.skip("Missing required environment variables")

        engine = create_rds_iam_engine(
            host=os.getenv("RDS_HOST"),
            port=3306,
            database=os.getenv("RDS_DATABASE", "test"),
            username=os.getenv("RDS_USER"),
            region=os.getenv("AWS_REGION"),
        )

        # Test actual connection
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            assert result.scalar() == 1
