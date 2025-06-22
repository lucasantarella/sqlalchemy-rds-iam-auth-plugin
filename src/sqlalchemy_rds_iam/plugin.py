"""AWS RDS IAM Authentication Plugin for SQLAlchemy."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from sqlalchemy import event  # type: ignore[import-not-found]

# Backwards compatibility for SQLAlchemy 1.4/2.0
try:
    from sqlalchemy import URL
except ImportError:
    from sqlalchemy.engine.url import URL  # type: ignore[import-not-found]

try:
    from sqlalchemy import CreateEnginePlugin
except ImportError:
    from sqlalchemy.engine import CreateEnginePlugin  # type: ignore[import-not-found]

from .exceptions import RDSIAMAuthError

logger = logging.getLogger(__name__)


class RDSIAMAuthPlugin(CreateEnginePlugin):  # type: ignore[misc]
    """
    SQLAlchemy plugin for AWS RDS IAM authentication.

    This plugin automatically generates and refreshes IAM authentication tokens
    for RDS database connections.

    Usage:
        engine = create_engine(
            "mysql+pymysql://myuser@myhost.region.rds.amazonaws.com/mydb"
            "?use_iam_auth=true&aws_region=us-east-1",
            plugin='rds_iam'
        )

    URL Parameters:
        use_iam_auth: Enable IAM authentication (default: false)
        aws_region: AWS region (optional, will try to infer from hostname)
        aws_profile: AWS profile to use (optional)
        ssl_ca: Path to RDS CA bundle (optional, but recommended)
    """

    # Token expires after 15 minutes, refresh at 10 minutes
    TOKEN_EXPIRY_MINUTES = 10

    def __init__(self, url: URL, kwargs: Dict[str, Any]):
        super().__init__(url, kwargs)

        # Parse URL parameters
        self.host = url.host
        self.port = url.port or self._get_default_port(url.drivername)
        self.user = url.username

        # Extract query parameters - handle SQLAlchemy 1.4+ immutable URLs
        if hasattr(CreateEnginePlugin, "update_url"):
            # SQLAlchemy 1.4+ API - URL is immutable, read parameters only
            query_params = dict(url.query)
            use_iam_auth_value = query_params.get("use_iam_auth", "false")
            if isinstance(use_iam_auth_value, str):
                self.use_iam_auth = use_iam_auth_value.lower() == "true"
            else:
                self.use_iam_auth = False
            self.aws_region = query_params.get("aws_region") or self._infer_region(
                self.host
            )
            self.aws_profile = query_params.get("aws_profile")
            self.ssl_ca = query_params.get("ssl_ca")
        else:
            # SQLAlchemy 1.3 and earlier API - can mutate URL directly
            query_params = url.query
            use_iam_auth_value = query_params.pop("use_iam_auth", "false")
            self.use_iam_auth = str(use_iam_auth_value).lower() == "true"  # noqa: E501
            self.aws_region = query_params.pop(
                "aws_region", None
            ) or self._infer_region(self.host)
            self.aws_profile = query_params.pop("aws_profile", None)
            self.ssl_ca = query_params.pop("ssl_ca", None)

        # Token caching
        self._token_cache: Dict[str, Tuple[str, datetime]] = {}
        self._session: Optional[boto3.Session] = None

        # Validate configuration
        if self.use_iam_auth:
            self._validate_config()

    def _get_default_port(self, drivername: str) -> int:
        """Get default port based on driver."""
        if "mysql" in drivername:
            return 3306
        elif "postgresql" in drivername or "postgres" in drivername:
            return 5432
        else:
            raise RDSIAMAuthError(f"Unsupported driver: {drivername}")

    def _infer_region(self, hostname: Optional[str]) -> Optional[str]:
        """Try to infer AWS region from RDS hostname."""
        if hostname and ".rds.amazonaws.com" in hostname:
            # Format: instance.region.rds.amazonaws.com
            parts = hostname.split(".")
            if len(parts) >= 4:
                return parts[-4]
        return None

    def _validate_config(self) -> None:
        """Validate required configuration."""
        if not self.host:
            raise RDSIAMAuthError("Host is required for IAM authentication")
        if not self.user:
            raise RDSIAMAuthError("Username is required for IAM authentication")
        if not self.aws_region:
            raise RDSIAMAuthError(
                "AWS region is required. "
                "Specify 'aws_region' in URL or use RDS hostname"
            )

    @property
    def session(self) -> boto3.Session:
        """Lazy-load boto3 session."""
        if self._session is None:
            session_kwargs: Dict[str, Any] = {}
            if self.aws_profile:
                session_kwargs["profile_name"] = self.aws_profile
            self._session = boto3.Session(**session_kwargs)
        return self._session

    def update_url(self, url: URL) -> URL:
        """Remove plugin-specific parameters from URL."""
        return url.difference_update_query(
            ["aws_region", "use_iam_auth", "aws_profile", "ssl_ca"]
        )

    def get_authentication_token(self) -> str:
        """
        Generate RDS IAM authentication token with caching.

        Returns:
            str: Authentication token

        Raises:
            RDSIAMAuthError: If token generation fails
        """
        cache_key = f"{self.host}:{self.port}:{self.user}"
        now = datetime.utcnow()

        # Check cache
        if cache_key in self._token_cache:
            token, expiry = self._token_cache[cache_key]
            if now < expiry:
                logger.debug("Using cached IAM token")
                return token

        # Generate new token
        try:
            logger.debug(
                f"Generating new IAM token for {self.user}@{self.host}:{self.port}"
            )
            client = self.session.client("rds", region_name=str(self.aws_region))
            auth_token: str = client.generate_db_auth_token(
                DBHostname=self.host,
                Port=self.port,
                DBUsername=self.user,
                Region=self.aws_region,
            )

            # Cache token
            expiry = now + timedelta(minutes=self.TOKEN_EXPIRY_MINUTES)
            self._token_cache[cache_key] = (auth_token, expiry)

            return auth_token

        except NoCredentialsError:
            raise RDSIAMAuthError(
                "No AWS credentials found. "
                "Configure AWS credentials or specify aws_profile"
            )
        except ClientError as e:
            raise RDSIAMAuthError(f"Failed to generate auth token: {e}")
        except Exception as e:
            raise RDSIAMAuthError(f"Unexpected error generating token: {e}")

    def _provide_token(
        self, dialect: Any, conn_rec: Any, cargs: Any, cparams: Dict[str, Any]
    ) -> None:
        """Provide authentication token to connection parameters."""
        try:
            cparams["password"] = self.get_authentication_token()

            # Add SSL parameters if not already specified
            if self.ssl_ca and "ssl" not in cparams:
                cparams["ssl"] = {"ca": self.ssl_ca}

        except RDSIAMAuthError:
            # Re-raise our exceptions
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            raise RDSIAMAuthError(f"Failed to provide auth token: {e}")

    def _handle_pool_invalidate(
        self, dbapi_conn: Any, connection_record: Any, exception: Optional[Exception]
    ) -> None:
        """Handle connection errors by invalidating stale connections."""
        if exception and "authentication" in str(exception).lower():
            # Clear token cache on auth failures
            cache_key = f"{self.host}:{self.port}:{self.user}"
            self._token_cache.pop(cache_key, None)
            logger.warning("Cleared token cache due to authentication error")

    def engine_created(self, engine: Any) -> None:
        """Set up event listeners when engine is created."""
        if self.use_iam_auth:
            # Add token provider
            event.listen(engine, "do_connect", self._provide_token)

            # Add connection pool listener for better error handling
            event.listen(engine.pool, "invalidate", self._handle_pool_invalidate)

            # Log successful setup
            logger.info(
                f"RDS IAM authentication enabled for "
                f"{self.user}@{self.host}:{self.port}"
            )

            # Warn about SSL
            if not self.ssl_ca:
                logger.warning(
                    "SSL CA not specified. Consider adding "
                    "'&ssl_ca=/path/to/rds-ca.pem' to your connection URL "
                    "for secure connections"
                )


def create_rds_iam_engine(
    host: str,
    port: int,
    database: str,
    username: str,
    *,
    dialect: str = "mysql+pymysql",
    region: Optional[str] = None,
    profile: Optional[str] = None,
    ssl_ca: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """
    Convenience function to create an engine with RDS IAM authentication.

    Args:
        host: RDS endpoint hostname
        port: Database port
        database: Database name
        username: Database username
        dialect: SQLAlchemy dialect (default: mysql+pymysql)
        region: AWS region (optional, will try to infer)
        profile: AWS profile name (optional)
        ssl_ca: Path to RDS CA certificate bundle (optional)
        **kwargs: Additional engine arguments

    Returns:
        SQLAlchemy Engine configured for RDS IAM auth

    Example:
        engine = create_rds_iam_engine(
            host="mydb.us-east-1.rds.amazonaws.com",
            port=3306,
            database="myapp",
            username="myuser",
            region="us-east-1"
        )
    """
    from sqlalchemy import create_engine

    # Build URL
    url_params = ["use_iam_auth=true"]
    if region:
        url_params.append(f"aws_region={region}")
    if profile:
        url_params.append(f"aws_profile={profile}")
    if ssl_ca:
        url_params.append(f"ssl_ca={ssl_ca}")

    query_string = "&".join(url_params)
    url = f"{dialect}://{username}@{host}:{port}/{database}?{query_string}"

    # Set default pool_pre_ping for better connection handling
    kwargs.setdefault("pool_pre_ping", True)

    return create_engine(url, **kwargs)
