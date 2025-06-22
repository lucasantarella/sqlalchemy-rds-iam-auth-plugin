# SQLAlchemy RDS IAM Authentication Plugin

A SQLAlchemy plugin that enables AWS RDS IAM database authentication, automatically generating and refreshing IAM authentication tokens for secure, password-free database connections.

## Features

- **Automatic token generation**: Generates IAM authentication tokens automatically
- **Token caching**: Caches tokens to avoid unnecessary AWS API calls
- **Token refresh**: Automatically refreshes expired tokens
- **Multiple database support**: Works with MySQL and PostgreSQL RDS instances
- **SSL support**: Built-in SSL configuration for secure connections
- **Connection pooling**: Integrates seamlessly with SQLAlchemy's connection pooling
- **Error handling**: Robust error handling with automatic token cache invalidation

## Installation

```bash
pip install sqlalchemy-rds-iam
```

## Prerequisites

1. **AWS Credentials**: Configure AWS credentials via AWS CLI, environment variables, or IAM roles
2. **RDS IAM Authentication**: Enable IAM database authentication on your RDS instance
3. **Database User**: Create a database user with IAM authentication enabled
4. **SSL Certificate**: Download the RDS CA certificate bundle (recommended)

### Setting up RDS IAM Authentication

1. Enable IAM authentication on your RDS instance:
```bash
aws rds modify-db-instance --db-instance-identifier mydb --enable-iam-database-authentication
```

2. Create a database user with IAM authentication:
```sql
-- For MySQL
CREATE USER 'myuser'@'%' IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS';
GRANT SELECT, INSERT, UPDATE, DELETE ON mydb.* TO 'myuser'@'%';

-- For PostgreSQL
CREATE USER myuser;
GRANT rds_iam TO myuser;
GRANT ALL PRIVILEGES ON DATABASE mydb TO myuser;
```

## Usage

### Basic Usage

```python
from sqlalchemy import create_engine

# Using connection URL with plugin parameters
engine = create_engine(
    "mysql+pymysql://myuser@mydb.us-east-1.rds.amazonaws.com/mydb"
    "?use_iam_auth=true&aws_region=us-east-1",
    plugins=["rds_iam"]
)

# Test the connection
with engine.connect() as conn:
    result = conn.execute("SELECT 1")
    print(result.fetchone())
```

### Using the Convenience Function

```python
from sqlalchemy_rds_iam import create_rds_iam_engine

# Create engine with IAM authentication
engine = create_rds_iam_engine(
    host="mydb.us-east-1.rds.amazonaws.com",
    port=3306,
    database="mydb",
    username="myuser",
    region="us-east-1"
)

# Use with SQLAlchemy ORM
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)

with Session() as session:
    # Your ORM operations here
    pass
```

### PostgreSQL Example

```python
from sqlalchemy_rds_iam import create_rds_iam_engine

engine = create_rds_iam_engine(
    host="mydb.us-west-2.rds.amazonaws.com",
    port=5432,
    database="postgres",
    username="myuser",
    dialect="postgresql+psycopg2",
    region="us-west-2"
)
```

### With SSL Certificate

```python
from sqlalchemy_rds_iam import create_rds_iam_engine

engine = create_rds_iam_engine(
    host="mydb.us-east-1.rds.amazonaws.com",
    port=3306,
    database="mydb",
    username="myuser",
    region="us-east-1",
    ssl_ca="/path/to/rds-ca-2019-root.pem"  # Download from AWS
)
```

### Using AWS Profiles

```python
from sqlalchemy import create_engine

engine = create_engine(
    "mysql+pymysql://myuser@mydb.us-east-1.rds.amazonaws.com/mydb"
    "?use_iam_auth=true&aws_region=us-east-1&aws_profile=production",
    plugins=["rds_iam"]
)
```

### Advanced Configuration

```python
from sqlalchemy_rds_iam import create_rds_iam_engine

engine = create_rds_iam_engine(
    host="mydb.us-east-1.rds.amazonaws.com",
    port=3306,
    database="mydb",
    username="myuser",
    region="us-east-1",
    profile="production",
    ssl_ca="/path/to/rds-ca-2019-root.pem",
    # Additional SQLAlchemy engine options
    pool_size=20,
    pool_timeout=30,
    pool_recycle=3600,
    echo=True
)
```

## URL Parameters

When using connection URLs, the following parameters control IAM authentication:

- `use_iam_auth`: Enable IAM authentication (`"true"` or `"false"`, default: `"false"`)
- `aws_region`: AWS region (optional, will try to infer from hostname)
- `aws_profile`: AWS profile name (optional, uses default credentials if not specified)
- `ssl_ca`: Path to SSL CA certificate bundle (optional but recommended)

## Error Handling

The plugin provides detailed error messages for common issues:

```python
from sqlalchemy_rds_iam import RDSIAMAuthError

try:
    engine = create_rds_iam_engine(
        host="mydb.us-east-1.rds.amazonaws.com",
        port=3306,
        database="mydb",
        username="myuser"
    )
    with engine.connect() as conn:
        conn.execute("SELECT 1")
except RDSIAMAuthError as e:
    print(f"IAM authentication failed: {e}")
```

## Token Caching

The plugin automatically caches IAM tokens to improve performance:

- Tokens are cached for 10 minutes (tokens expire after 15 minutes)
- Cache is automatically cleared on authentication failures
- Each unique host/port/username combination has its own cache entry

## Supported Databases

- **MySQL**: Use `mysql+pymysql://` dialect
- **PostgreSQL**: Use `postgresql+psycopg2://` dialect

## Requirements

- Python 3.8+
- SQLAlchemy 2.0+
- boto3 1.33+
- Database-specific drivers (PyMySQL for MySQL, psycopg2 for PostgreSQL)

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=sqlalchemy_rds_iam --cov-report=html
```

### Code Quality

```bash
# Format code
black src tests

# Lint code
flake8 src tests

# Type checking
mypy src
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read the contributing guidelines and submit pull requests to the main branch.

## Security

This plugin handles AWS credentials and database authentication. Always follow AWS security best practices:

- Use IAM roles when possible instead of long-term credentials
- Enable SSL/TLS for database connections
- Regularly rotate access keys if using them
- Monitor CloudTrail logs for authentication events
