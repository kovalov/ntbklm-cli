# ntbklm-cli

CLI for [Google NotebookLM](https://notebooklm.google.com) — manage notebooks, sources, and conversations from your terminal.

Built on top of [notebooklm-py](https://github.com/teng-lin/notebooklm-py).

## Install

```bash
pipx install git+https://github.com/kovalov/ntbklm-cli.git
playwright install chromium
```

Or with pip:

```bash
pip install git+https://github.com/kovalov/ntbklm-cli.git
playwright install chromium
```

## Quick start

```bash
# Authenticate (opens browser)
ntbklm login

# List your notebooks
ntbklm list

# Select a notebook
ntbklm use c220

# Add sources
ntbklm add https://example.com/article
ntbklm add ./report.pdf

# Ask questions (tracks conversation for follow-ups)
ntbklm ask "What are the key takeaways?"
ntbklm ask "Can you elaborate on point 2?"

# Other commands
ntbklm sources    # list sources in current notebook
ntbklm summary    # AI summary of current notebook
ntbklm create "My Research"  # create new notebook
ntbklm status     # show current context
```

## Commands

| Command | Description |
|---------|-------------|
| `login` | Authenticate with Google (opens browser) |
| `list` | List all notebooks |
| `create TITLE` | Create notebook, auto-set as current |
| `use ID` | Set current notebook (prefix match) |
| `add SOURCE` | Add file or URL as source |
| `ask QUESTION` | Ask question (tracks conversation) |
| `summary` | AI summary of current notebook |
| `sources` | List sources in current notebook |
| `status` | Show current context |

## Requirements

- Python 3.10+
- Google account with NotebookLM access
