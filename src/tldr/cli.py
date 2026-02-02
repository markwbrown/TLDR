"""Command-line interface for TLDR email summarizer."""

from __future__ import annotations

import logging
import sys
from typing import Optional

import typer

from .config import get_settings
from .gmail import GmailClient
from .ai import Summarizer
from .calendar import replace_events_with_links

app = typer.Typer(
    name="tldr",
    help="Email summarizer using OpenAI - TL;DR for your inbox",
    no_args_is_help=True,
)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


@app.command()
def process(
    label: Optional[str] = typer.Option(
        None, "--label", "-l", help="Gmail label to process (default from config)"
    ),
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum emails to process"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Don't send emails or modify labels"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Process emails from inbox - summarize and send digests."""
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    settings = get_settings()
    source_label = label or settings.gmail_source_label
    processed_label = settings.gmail_processed_label

    logger.info(f"Processing emails with label: {source_label}")

    # Initialize clients
    gmail = GmailClient()
    summarizer = Summarizer(settings=settings)

    # Fetch messages
    messages = gmail.fetch_messages(source_label, max_results=limit)

    if not messages:
        logger.info("No messages to process")
        return

    logger.info(f"Found {len(messages)} message(s) to process")

    for msg in messages:
        logger.info(f"Processing: {msg.subject} from {msg.sender}")

        # Summarize
        summary = summarizer.summarize(msg.body, sender=msg.sender)

        # Process events
        summary_with_links = replace_events_with_links(summary.text)

        # Build email
        subject = f"TLDR Summary: {msg.subject} - {msg.sender}"
        body = f"Summary:\n\n{summary_with_links}"

        if dry_run:
            logger.info(f"[DRY RUN] Would send:\n{subject}\n\n{body[:500]}...")
        else:
            # Send summary email
            if settings.to_email:
                gmail.send_email(settings.to_email, subject, body)
                logger.info(f"Sent summary to {settings.to_email}")
            else:
                logger.warning("No TO_EMAIL configured, skipping send")

            # Move to processed
            gmail.modify_labels(
                msg.id,
                add_labels=[processed_label],
                remove_labels=[source_label],
            )
            logger.info(f"Moved to {processed_label}")

        logger.info(f"Estimated tokens used: {summary.estimated_tokens_used}")

    logger.info("Processing complete!")


@app.command()
def summarize(
    text: Optional[str] = typer.Argument(None, help="Text to summarize"),
    stdin: bool = typer.Option(False, "--stdin", help="Read from stdin"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Summarize text directly (without Gmail integration)."""
    setup_logging(verbose)

    if stdin:
        text = sys.stdin.read()
    elif not text:
        typer.echo("Error: Provide text as argument or use --stdin", err=True)
        raise typer.Exit(1)

    settings = get_settings()
    summarizer = Summarizer(settings=settings)

    result = summarizer.summarize(text)
    
    # Process events
    output = replace_events_with_links(result.text)
    typer.echo(output)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="API host"),
    port: int = typer.Option(8000, "--port", "-p", help="API port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
) -> None:
    """Start the API server (requires FastAPI)."""
    try:
        import uvicorn
        from .api import create_app
    except ImportError:
        typer.echo("Error: Install API dependencies: pip install fastapi uvicorn", err=True)
        raise typer.Exit(1)

    app = create_app()
    uvicorn.run(app, host=host, port=port, reload=reload)


@app.command()
def config(
    validate: bool = typer.Option(False, "--validate", help="Validate configuration"),
    show: bool = typer.Option(False, "--show", help="Show current config (masks secrets)"),
) -> None:
    """Check or display configuration."""
    try:
        settings = get_settings()

        if validate:
            typer.echo("✅ Configuration is valid")

        if show:
            typer.echo("\nCurrent Configuration:")
            typer.echo(f"  OpenAI Model: {settings.openai_model}")
            typer.echo(f"  Token Limit: {settings.token_limit_per_minute}/min")
            typer.echo(f"  Max Tokens/Request: {settings.max_tokens_per_request}")
            typer.echo(f"  Source Label: {settings.gmail_source_label}")
            typer.echo(f"  Processed Label: {settings.gmail_processed_label}")
            typer.echo(f"  To Email: {settings.to_email or '(not set)'}")
            typer.echo(f"  API Key: {'✓ set' if settings.openai_api_key else '✗ not set'}")

    except Exception as e:
        typer.echo(f"❌ Configuration error: {e}", err=True)
        raise typer.Exit(1)


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
