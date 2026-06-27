"""Composition root — builds concrete adapters from settings and wires them.

This is the only module that imports concrete adapters. The API and domain
layers depend on the ports, not on these constructors.
"""

from __future__ import annotations

from app.adapters.sqlite_repo import SqliteRepository
from app.adapters.stub_llm import StubLLM
from app.ports.documents import DocumentStore
from app.ports.email import EmailSender
from app.ports.llm import LLM
from app.ports.repository import Repository
from app.security import CognitoVerifier
from app.settings import Settings


def build_repo(settings: Settings) -> Repository:
    if settings.repo_backend == "sqlite":
        settings.ensure_dirs()
        repo = SqliteRepository(settings.db_path)
        repo.init()
        return repo
    if settings.repo_backend == "dynamodb":
        from app.adapters.dynamo_repo import DynamoRepository

        dynamo = DynamoRepository(settings.dynamo_table, region=settings.aws_region)
        dynamo.init()
        return dynamo
    raise NotImplementedError(f"repo_backend '{settings.repo_backend}' not yet implemented")


def build_llm(settings: Settings) -> LLM:
    provider = settings.resolve_provider()
    if provider == "bedrock":
        import boto3

        from app.adapters.bedrock_llm import BedrockLLM

        client = boto3.client("bedrock-runtime", region_name=settings.bedrock_resolved_region)
        return BedrockLLM(
            client=client,
            model_id=settings.bedrock_model_id(),
            accountable_human=settings.accountable_human,
        )
    # Anthropic adapter lands later; fall back to the stub so the service still
    # runs if a provider is selected before its adapter exists.
    return StubLLM(accountable_human=settings.accountable_human)


def build_verifier(settings: Settings) -> CognitoVerifier | None:
    """Build the Cognito token verifier, or ``None`` when auth is disabled."""
    if not settings.auth_enabled:
        return None
    return CognitoVerifier(
        jwks_url=settings.cognito_jwks_url,
        issuer=settings.cognito_issuer,
        client_id=settings.cognito_client_id,
    )


def build_email_sender(settings: Settings) -> EmailSender:
    """Select the outbound-email adapter from settings.

    Default ``log`` is an offline no-op (dev/CI safe). ``ses`` sends through
    Amazon SES from ``email_from`` in ``email_resolved_region``.
    """
    if settings.email_provider == "ses":
        import boto3

        from app.adapters.ses_email import SesEmailSender

        client = boto3.client("ses", region_name=settings.email_resolved_region)
        return SesEmailSender(client=client, sender=settings.email_from)
    from app.adapters.ses_email import LogEmailSender

    return LogEmailSender(sender=settings.email_from)


def build_document_store(settings: Settings) -> DocumentStore | None:
    """Build the S3 document store, or ``None`` when no bucket is configured.

    ``None`` disables the upload endpoints (503) while the paste-text path keeps
    working — the dev-safe default (zero standing storage).
    """
    if not settings.documents_bucket:
        return None
    import boto3

    from app.adapters.s3_documents import S3DocumentStore

    client = boto3.client("s3", region_name=settings.documents_resolved_region)
    return S3DocumentStore(client=client, bucket=settings.documents_bucket)
