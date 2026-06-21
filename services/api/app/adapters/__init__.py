"""Concrete adapters that implement the ports for a given environment.

Local dev: :class:`SqliteRepository` + :class:`StubLLM`.
Production: ``DynamoRepository`` + ``BedrockLLM`` (added in later increments).
"""
