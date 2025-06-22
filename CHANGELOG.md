# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of SQLAlchemy RDS IAM Authentication Plugin
- Support for MySQL and PostgreSQL RDS instances
- Automatic IAM token generation and caching
- SQLAlchemy 1.4+ and 2.0+ compatibility
- Comprehensive test suite
- Type hints and mypy support

### Features
- AWS RDS IAM authentication for SQLAlchemy
- Token caching with automatic refresh
- SSL/TLS support for secure connections
- Region inference from RDS hostnames
- Custom AWS profile support
- Connection pool integration
- Error handling and logging

### Security
- Secure token handling and caching
- SSL certificate validation support
- No credential storage in code

## [0.1.0] - 2024-06-22

### Added
- Initial release
