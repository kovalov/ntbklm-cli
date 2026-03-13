"""NotebookLM CLI — manage notebooks, sources, and conversations."""

import asyncio
import functools
import itertools
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import click

from notebooklm import NotebookLMClient, AuthError, NotebookLMError
from notebooklm.cli.helpers import (
    get_current_notebook,
    set_current_notebook,
    get_current_conversation,
    set_current_conversation,
    require_notebook,
)


@contextmanager
def spinner(message):
    """Show an animated spinner while work is in progress."""
    stop = threading.Event()
    frames = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])

    def _spin():
        while not stop.is_set():
            sys.stderr.write(f"\r{next(frames)} {message}...")
            sys.stderr.flush()
            time.sleep(0.08)

    t = threading.Thread(target=_spin, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop.set()
        t.join()
        sys.stderr.write(f"\r\033[2K")
        sys.stderr.flush()


def async_cmd(fn):
    """Decorator that wraps an async Click command with asyncio.run()."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


class _ClientContext:
    """Async context manager for authenticated NotebookLM client."""

    async def __aenter__(self):
        try:
            self._client = await NotebookLMClient.from_storage()
            return await self._client.__aenter__()
        except (FileNotFoundError, AuthError):
            click.echo("Not authenticated. Run: ntbklm login", err=True)
            sys.exit(1)

    async def __aexit__(self, *exc):
        return await self._client.__aexit__(*exc)


def client():
    return _ClientContext()


def current_notebook():
    return require_notebook(get_current_notebook())


# ── CLI group ────────────────────────────────────────────────────────────────


@click.group()
@click.version_option(package_name="ntbklm-cli")
def cli():
    """NotebookLM CLI — manage notebooks, sources, and conversations."""


# ── login ────────────────────────────────────────────────────────────────────


@cli.command()
@click.pass_context
def login(ctx):
    """Authenticate with Google (opens browser)."""
    # Auto-install Chromium if missing (uses pipx venv's own Python)
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
    )

    from notebooklm.cli.session import register_session_commands

    @click.group()
    def _tmp():
        pass

    register_session_commands(_tmp)
    ctx.invoke(_tmp.commands["login"])


# ── list ─────────────────────────────────────────────────────────────────────


@cli.command("list")
@async_cmd
async def list_notebooks():
    """List all notebooks."""
    async with client() as c:
        with spinner("Fetching notebooks"):
            notebooks = await c.notebooks.list()
        current = get_current_notebook()
        if not notebooks:
            click.echo("No notebooks found.")
            return
        for nb in notebooks:
            marker = " *" if nb.id == current else ""
            count = f"  ({nb.sources_count} sources)" if nb.sources_count else ""
            click.echo(f"  {nb.id[:8]}  {nb.title}{count}{marker}")


# ── create ───────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("title")
@async_cmd
async def create(title):
    """Create a new notebook and set it as current."""
    async with client() as c:
        with spinner("Creating notebook"):
            nb = await c.notebooks.create(title)
        set_current_notebook(nb.id, title=nb.title)
        click.echo(f"Created: {nb.title}  ({nb.id[:8]})")


# ── use ──────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("notebook_id")
@async_cmd
async def use(notebook_id):
    """Set the current notebook by ID (prefix match supported)."""
    async with client() as c:
        notebooks = await c.notebooks.list()
        match = next(
            (nb for nb in notebooks if nb.id.startswith(notebook_id)),
            None,
        )
        if not match:
            click.echo(f"No notebook matching '{notebook_id}'.", err=True)
            sys.exit(1)
        set_current_notebook(match.id, title=match.title)
        set_current_conversation(None)
        click.echo(f"Now using: {match.title}  ({match.id[:8]})")


# ── add ──────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("source")
@async_cmd
async def add(source):
    """Add a source (file path or URL) to the current notebook."""
    nb_id = current_notebook()
    async with client() as c:
        if source.startswith(("http://", "https://")):
            with spinner(f"Adding URL: {source}"):
                src = await c.sources.add_url(nb_id, source, wait=True)
        else:
            path = Path(source).expanduser().resolve()
            if not path.exists():
                click.echo(f"File not found: {source}", err=True)
                sys.exit(1)
            with spinner(f"Adding file: {path.name}"):
                src = await c.sources.add_file(nb_id, str(path), wait=True)
        click.echo(f"Added: {src.title}  ({src.id[:8]})")


# ── ask ──────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("question")
@async_cmd
async def ask(question):
    """Ask a question about the current notebook."""
    nb_id = current_notebook()
    conv_id = get_current_conversation()
    async with client() as c:
        with spinner("Thinking"):
            result = await c.chat.ask(nb_id, question, conversation_id=conv_id)
        set_current_conversation(result.conversation_id)
        click.echo(result.answer)


# ── summary ──────────────────────────────────────────────────────────────────


@cli.command()
@async_cmd
async def summary():
    """Get an AI summary of the current notebook."""
    nb_id = current_notebook()
    async with client() as c:
        with spinner("Generating summary"):
            text = await c.notebooks.get_summary(nb_id)
        click.echo(text)


# ── sources ──────────────────────────────────────────────────────────────────


@cli.command()
@async_cmd
async def sources():
    """List sources in the current notebook."""
    nb_id = current_notebook()
    async with client() as c:
        with spinner("Fetching sources"):
            srcs = await c.sources.list(nb_id)
        if not srcs:
            click.echo("No sources in this notebook.")
            return
        for s in srcs:
            flag = " [error]" if s.is_error else " [processing]" if s.is_processing else ""
            click.echo(f"  {s.id[:8]}  {s.title}{flag}")


# ── status ───────────────────────────────────────────────────────────────────


@cli.command()
def status():
    """Show current notebook and conversation context."""
    nb_id = get_current_notebook()
    conv_id = get_current_conversation()
    click.echo(f"Notebook:     {nb_id[:8] if nb_id else '(none — run: ntbklm use ID)'}")
    click.echo(f"Conversation: {conv_id[:8] if conv_id else '(none — starts on next ask)'}")


# ── entry point ──────────────────────────────────────────────────────────────


def main():
    try:
        cli()
    except NotebookLMError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
