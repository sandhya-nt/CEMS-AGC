"""Shared CEMS domain models and services.

The package intentionally contains no Flask application instance. Models are bound
to the SQLAlchemy extension initialized by the main application, which keeps the
domain layer importable from tests and future blueprints.
"""
