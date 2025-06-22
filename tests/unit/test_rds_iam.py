"""Unit tests for RDS IAM Auth Plugin."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

# Backwards compatibility for SQLAlchemy 1.4/2.0
try:
    from sqlalchemy import URL
except ImportError:
    from sqlalchemy.engine.url import URL

from sqlalchemy_rds_iam.exceptions import RDSIAMAuthError
from sqlalchemy_rds_iam.plugin import RDSIAMAuthPlugin, create_rds_iam_engine


class TestRDSIAMAuthPlugin:
    """Test cases for RDSIAMAuthPlugin class."""

    @pytest.fixture
    def basic_url(self):
        """Create a basic URL for testing."""
        return URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="mydb.us-east-1.rds.amazonaws.com",
            port=3306,
            database="testdb",
            query={"use_iam_auth": "true", "aws_region": "us-east-1"},
        )

    @pytest.fixture
    def plugin(self, basic_url):
        """Create a plugin instance for testing."""
        return RDSIAMAuthPlugin(basic_url, {})

    def test_initialization_with_all_parameters(self):
        """Test plugin initialization with all parameters."""
        url = URL.create(
            drivername="postgresql+psycopg2",
            username="testuser",
            host="mydb.us-west-2.rds.amazonaws.com",
            port=5432,
            database="testdb",
            query={
                "use_iam_auth": "true",
                "aws_region": "us-west-2",
                "aws_profile": "production",
                "ssl_ca": "/path/to/ca.pem",
            },
        )

        plugin = RDSIAMAuthPlugin(url, {})

        assert plugin.host == "mydb.us-west-2.rds.amazonaws.com"
        assert plugin.port == 5432
        assert plugin.user == "testuser"
        assert plugin.aws_region == "us-west-2"
        assert plugin.aws_profile == "production"
        assert plugin.ssl_ca == "/path/to/ca.pem"
        assert plugin.use_iam_auth is True

    def test_initialization_without_iam_auth(self):
        """Test plugin initialization when IAM auth is disabled."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="localhost",
            database="testdb",
        )

        plugin = RDSIAMAuthPlugin(url, {})
        assert plugin.use_iam_auth is False

    def test_region_inference_from_hostname(self):
        """Test AWS region inference from RDS hostname."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="mydb.eu-central-1.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        plugin = RDSIAMAuthPlugin(url, {})
        assert plugin.aws_region == "eu-central-1"

    def test_default_port_mysql(self):
        """Test default port for MySQL."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="mydb.us-east-1.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        plugin = RDSIAMAuthPlugin(url, {})
        assert plugin.port == 3306

    def test_default_port_postgresql(self):
        """Test default port for PostgreSQL."""
        url = URL.create(
            drivername="postgresql+psycopg2",
            username="testuser",
            host="mydb.us-east-1.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        plugin = RDSIAMAuthPlugin(url, {})
        assert plugin.port == 5432

    def test_unsupported_driver(self):
        """Test error with unsupported database driver."""
        url = URL.create(
            drivername="oracle+cx_oracle",
            username="testuser",
            host="mydb.us-east-1.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        with pytest.raises(RDSIAMAuthError, match="Unsupported driver"):
            RDSIAMAuthPlugin(url, {})

    def test_missing_host_validation(self):
        """Test validation error when host is missing."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            database="testdb",
            query={"use_iam_auth": "true", "aws_region": "us-east-1"},
        )

        with pytest.raises(RDSIAMAuthError, match="Host is required"):
            RDSIAMAuthPlugin(url, {})

    def test_missing_username_validation(self):
        """Test validation error when username is missing."""
        url = URL.create(
            drivername="mysql+pymysql",
            host="mydb.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true", "aws_region": "us-east-1"},
        )

        with pytest.raises(RDSIAMAuthError, match="Username is required"):
            RDSIAMAuthPlugin(url, {})

    def test_missing_region_validation(self):
        """Test validation error when region cannot be determined."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="localhost",  # Non-RDS hostname
            database="testdb",
            query={"use_iam_auth": "true"},
        )

        with pytest.raises(RDSIAMAuthError, match="AWS region is required"):
            RDSIAMAuthPlugin(url, {})

    def test_update_url_removes_plugin_params(self, plugin, basic_url):
        """Test that update_url removes plugin-specific parameters."""
        updated_url = plugin.update_url(basic_url)

        # Check that plugin parameters are removed
        assert "use_iam_auth" not in updated_url.query
        assert "aws_region" not in updated_url.query
        assert "aws_profile" not in updated_url.query
        assert "ssl_ca" not in updated_url.query

    @patch("boto3.Session")
    def test_session_lazy_loading(self, mock_session_class, plugin):
        """Test that boto3 session is lazy-loaded."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Session should not be created yet
        mock_session_class.assert_not_called()

        # Access session property
        session = plugin.session

        # Now session should be created
        mock_session_class.assert_called_once()
        assert session == mock_session

        # Accessing again should return same session
        session2 = plugin.session
        assert session2 == mock_session
        mock_session_class.assert_called_once()  # Still only called once

    @patch("boto3.Session")
    def test_session_with_profile(self, mock_session_class):
        """Test session creation with AWS profile."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="mydb.us-east-1.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true", "aws_profile": "production"},
        )

        plugin = RDSIAMAuthPlugin(url, {})
        _ = plugin.session

        mock_session_class.assert_called_once_with(profile_name="production")

    @patch("boto3.Session")
    def test_get_authentication_token_success(self, mock_session_class, plugin):
        """Test successful token generation."""
        # Mock RDS client
        mock_client = Mock()
        mock_session = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Mock token generation
        expected_token = "test-auth-token-12345"
        mock_client.generate_db_auth_token.return_value = expected_token

        # Get token
        token = plugin.get_authentication_token()

        # Verify
        assert token == expected_token
        mock_client.generate_db_auth_token.assert_called_once_with(
            DBHostname="mydb.us-east-1.rds.amazonaws.com",
            Port=3306,
            DBUsername="testuser",
            Region="us-east-1",
        )

    @patch("boto3.Session")
    def test_get_authentication_token_caching(self, mock_session_class, plugin):
        """Test that tokens are cached and reused."""
        # Mock RDS client
        mock_client = Mock()
        mock_session = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Mock token generation
        mock_client.generate_db_auth_token.return_value = "cached-token"

        # Get token multiple times
        token1 = plugin.get_authentication_token()
        token2 = plugin.get_authentication_token()
        token3 = plugin.get_authentication_token()

        # Should all be the same token
        assert token1 == token2 == token3 == "cached-token"

        # Should only call AWS once due to caching
        mock_client.generate_db_auth_token.assert_called_once()

    @patch("boto3.Session")
    @patch("sqlalchemy_rds_iam.plugin.datetime")
    def test_get_authentication_token_cache_expiry(
        self, mock_datetime, mock_session_class, plugin
    ):
        """Test that cached tokens expire and are refreshed."""
        # Mock RDS client
        mock_client = Mock()
        mock_session = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Mock time progression
        base_time = datetime(2023, 1, 1, 12, 0, 0)
        mock_datetime.utcnow.side_effect = [
            base_time,  # First call
            base_time + timedelta(minutes=5),  # Within cache period
            base_time + timedelta(minutes=11),  # After cache expiry
        ]

        # Mock different tokens
        mock_client.generate_db_auth_token.side_effect = ["token1", "token2"]

        # First call - generates new token
        token1 = plugin.get_authentication_token()
        assert token1 == "token1"

        # Second call - uses cached token
        token2 = plugin.get_authentication_token()
        assert token2 == "token1"

        # Third call - cache expired, generates new token
        token3 = plugin.get_authentication_token()
        assert token3 == "token2"

        # Should have called AWS twice
        assert mock_client.generate_db_auth_token.call_count == 2

    @patch("boto3.Session")
    def test_get_authentication_token_no_credentials(self, mock_session_class, plugin):
        """Test error handling when AWS credentials are missing."""
        # Mock RDS client to raise NoCredentialsError
        mock_client = Mock()
        mock_session = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        mock_client.generate_db_auth_token.side_effect = NoCredentialsError()

        with pytest.raises(RDSIAMAuthError, match="No AWS credentials found"):
            plugin.get_authentication_token()

    @patch("boto3.Session")
    def test_get_authentication_token_client_error(self, mock_session_class, plugin):
        """Test error handling for AWS client errors."""
        # Mock RDS client to raise ClientError
        mock_client = Mock()
        mock_session = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        error = ClientError(
            {"Error": {"Code": "InvalidParameterValue", "Message": "Invalid user"}},
            "GenerateDBAuthToken",
        )
        mock_client.generate_db_auth_token.side_effect = error

        with pytest.raises(RDSIAMAuthError, match="Failed to generate auth token"):
            plugin.get_authentication_token()

    @patch.object(RDSIAMAuthPlugin, "get_authentication_token")
    def test_provide_token(self, mock_get_token, plugin):
        """Test _provide_token method."""
        mock_get_token.return_value = "test-token-123"

        # Mock connection parameters
        cparams = {}

        # Call _provide_token
        plugin._provide_token(None, None, None, cparams)

        # Check token was added
        assert cparams["password"] == "test-token-123"

    @patch.object(RDSIAMAuthPlugin, "get_authentication_token")
    def test_provide_token_with_ssl(self, mock_get_token):
        """Test _provide_token adds SSL parameters."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="mydb.us-east-1.rds.amazonaws.com",
            database="testdb",
            query={"use_iam_auth": "true", "ssl_ca": "/path/to/ca.pem"},
        )

        plugin = RDSIAMAuthPlugin(url, {})
        mock_get_token.return_value = "test-token"

        cparams = {}
        plugin._provide_token(None, None, None, cparams)

        assert cparams["password"] == "test-token"
        assert cparams["ssl"] == {"ca": "/path/to/ca.pem"}

    def test_handle_pool_invalidate_clears_cache(self, plugin):
        """Test that authentication errors clear the token cache."""
        # Add a token to cache
        cache_key = f"{plugin.host}:{plugin.port}:{plugin.user}"
        plugin._token_cache[cache_key] = ("cached-token", datetime.utcnow())

        # Mock authentication error
        error = Exception("Authentication failed for user")

        # Handle invalidation
        plugin._handle_pool_invalidate(None, None, error)

        # Cache should be cleared
        assert cache_key not in plugin._token_cache

    @patch("sqlalchemy.event.listen")
    def test_engine_created_with_iam_auth(self, mock_listen, plugin):
        """Test engine_created sets up event listeners."""
        mock_engine = Mock()
        mock_engine.pool = Mock()

        plugin.engine_created(mock_engine)

        # Should register two event listeners
        assert mock_listen.call_count == 2

        # Check first call - do_connect listener
        assert mock_listen.call_args_list[0][0][0] == mock_engine
        assert mock_listen.call_args_list[0][0][1] == "do_connect"

        # Check second call - invalidate listener
        assert mock_listen.call_args_list[1][0][0] == mock_engine.pool
        assert mock_listen.call_args_list[1][0][1] == "invalidate"

    @patch("sqlalchemy.event.listen")
    def test_engine_created_without_iam_auth(self, mock_listen):
        """Test engine_created does nothing when IAM auth is disabled."""
        url = URL.create(
            drivername="mysql+pymysql",
            username="testuser",
            host="localhost",
            database="testdb",
            query={"use_iam_auth": "false"},
        )

        plugin = RDSIAMAuthPlugin(url, {})
        mock_engine = Mock()

        plugin.engine_created(mock_engine)

        # Should not register any listeners
        mock_listen.assert_not_called()


class TestCreateRDSIAMEngine:
    """Test cases for create_rds_iam_engine convenience function."""

    @patch("sqlalchemy.create_engine")
    def test_basic_usage(self, mock_create_engine):
        """Test basic usage of create_rds_iam_engine."""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        result = create_rds_iam_engine(
            host="mydb.us-east-1.rds.amazonaws.com",
            port=3306,
            database="testdb",
            username="testuser",
        )

        # Check engine was created
        assert result == mock_engine

        # Check URL construction
        expected_url = (
            "mysql+pymysql://testuser@mydb.us-east-1.rds.amazonaws.com:3306/"
            "testdb?use_iam_auth=true"
        )
        mock_create_engine.assert_called_once()
        actual_url = mock_create_engine.call_args[0][0]
        assert actual_url == expected_url

    @patch("sqlalchemy.create_engine")
    def test_with_all_parameters(self, mock_create_engine):
        """Test create_rds_iam_engine with all parameters."""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        create_rds_iam_engine(
            host="mydb.us-west-2.rds.amazonaws.com",
            port=5432,
            database="testdb",
            username="testuser",
            dialect="postgresql+psycopg2",
            region="us-west-2",
            profile="production",
            ssl_ca="/path/to/ca.pem",
            echo=True,
            pool_size=20,
        )

        # Check URL construction
        expected_url = (
            "postgresql+psycopg2://testuser@mydb.us-west-2.rds.amazonaws.com:5432/"
            "testdb?use_iam_auth=true&aws_region=us-west-2&aws_profile=production"
            "&ssl_ca=/path/to/ca.pem"
        )

        call_args, call_kwargs = mock_create_engine.call_args
        assert call_args[0] == expected_url
        assert call_kwargs["echo"] is True
        assert call_kwargs["pool_size"] == 20
        assert call_kwargs["pool_pre_ping"] is True  # Default

    @patch("sqlalchemy.create_engine")
    def test_pool_pre_ping_default(self, mock_create_engine):
        """Test that pool_pre_ping defaults to True."""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        create_rds_iam_engine(
            host="mydb.rds.amazonaws.com", port=3306, database="test", username="user"
        )

        _, kwargs = mock_create_engine.call_args
        assert kwargs["pool_pre_ping"] is True

    @patch("sqlalchemy.create_engine")
    def test_pool_pre_ping_override(self, mock_create_engine):
        """Test that pool_pre_ping can be overridden."""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        create_rds_iam_engine(
            host="mydb.rds.amazonaws.com",
            port=3306,
            database="test",
            username="user",
            pool_pre_ping=False,
        )

        _, kwargs = mock_create_engine.call_args
        assert kwargs["pool_pre_ping"] is False
