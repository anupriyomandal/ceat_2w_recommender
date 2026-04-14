#!/usr/bin/env python3
"""
CEAT 2W Tyre Recommender — CLI Agent
─────────────────────────────────────
Usage:
  python -m cli.main            interactive agent session
  python -m cli.main ask "..."  one-shot query, then exit

Slash commands inside the session:
  /help      show help and example queries
  /clear     clear screen and conversation history
  /history   print conversation so far
  /sources   show retrieved records from the last query
  /quit      exit
"""
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from core.rag_engine import TyreRAG

# ─── Theme ────────────────────────────────────────────────────────────────────
THEME = Theme(
    {
        "agent":    "bold white",
        "user":     "bold cyan",
        "step":     "dim white",
        "step.ok":  "green",
        "step.run": "yellow",
        "muted":    "dim",
        "accent":   "white",
        "error":    "bold red",
        "cmd":      "bold magenta",
    }
)

console = Console(theme=THEME, highlight=False)
app     = typer.Typer(add_completion=False, invoke_without_command=True, help="CEAT 2W Tyre Recommender Agent")

# ─── Constants ────────────────────────────────────────────────────────────────
LOGO = """\
 ██████ ███████  █████  ████████     ████████ ██    ██ ██████  ███████ ███████
██      ██      ██   ██    ██           ██     ██  ██  ██   ██ ██      ██
██      █████   ███████    ██           ██      ████   ██████  █████   ███████
██      ██      ██   ██    ██           ██       ██    ██   ██ ██           ██
 ██████ ███████ ██   ██    ██           ██       ██    ██   ██ ███████ ███████"""

EXAMPLES = [
    "Bajaj Pulsar NS 200 — front and rear tyres",
    "Hero Splendor Plus 100cc",
    "Royal Enfield Classic 350",
    "Honda Unicorn 160cc tyre specs",
    "Yamaha R15 V4 tubeless tyre",
    "KTM Duke 390 tyre recommendation",
]

HELP_TEXT = """\
**Available commands**

| Command      | Description                          |
|:-------------|:-------------------------------------|
| `/help`      | Show this help screen                |
| `/clear`     | Clear screen and reset history       |
| `/history`   | Print conversation history           |
| `/sources`   | Show retrieved records (last query)  |
| `/quit`      | Exit the agent                       |

Type any motorcycle name or question to get a CEAT tyre recommendation.
"""

# ─── State ────────────────────────────────────────────────────────────────────
_history:     List[dict]  = []   # display history {"role": "user"|"agent", "content": str}
_engine_history: List[dict] = [] # OpenAI-format history passed to the model
_last_sources: List[dict] = []   # retrieved records from last query


# ─── Display helpers ──────────────────────────────────────────────────────────

def print_logo():
    console.print()
    console.print(LOGO, style="bold white", highlight=False)
    console.print()


def print_banner(record_count: int):
    subtitle = (
        f"[muted]  {record_count} vehicle-tyre mappings · "
        "CEAT Tyre Database · Indian 2-Wheeler Market[/muted]"
    )
    console.print(subtitle)
    console.print()


def print_examples():
    console.print("[muted]Try asking about:[/muted]")
    console.print()
    cols = []
    for i, ex in enumerate(EXAMPLES, 1):
        cols.append(Text(f"  {i}.  {ex}", style="dim italic"))
    # two-column layout
    console.print(Columns(cols, equal=True, expand=False))
    console.print()


def print_rule(label: str = ""):
    if label:
        console.print(Rule(f"[muted]{label}[/muted]", style="dim"))
    else:
        console.print(Rule(style="dim"))
    console.print()


def print_user_bubble(text: str):
    console.print()
    console.print(
        Panel(
            Text(text, style="white"),
            title="[user]  You[/user]",
            title_align="right",
            border_style="cyan",
            padding=(0, 2),
            box=box.ROUNDED,
        )
    )


def print_sources(sources: List[dict]):
    if not sources:
        console.print("[muted]No sources from last query.[/muted]")
        return

    table = Table(
        title="Retrieved Records",
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold white",
        border_style="dim",
        show_lines=False,
        pad_edge=True,
    )
    table.add_column("#",             style="dim",       width=3,  justify="right")
    table.add_column("Vehicle",       style="white",     min_width=28)
    table.add_column("Position",      style="dim",       width=8)
    table.add_column("SKU",           style="cyan",      width=10)
    table.add_column("Tyre",          style="dim white", min_width=24)
    table.add_column("Rim",           style="dim",       width=5)
    table.add_column("Construction",  style="dim",       width=12)

    for i, hit in enumerate(sources, 1):
        m = hit["metadata"]
        vehicle = f"{m.get('vehicle_brand','')} {m.get('vehicle_model','')} {m.get('vehicle_variant','')}".strip()
        table.add_row(
            str(i),
            vehicle,
            m.get("tyre_position", ""),
            m.get("sku", ""),
            m.get("tyre_name", ""),
            m.get("rim_size", ""),
            m.get("construction", ""),
        )

    console.print()
    console.print(table)
    console.print()


def print_history():
    if not _history:
        console.print("[muted]No conversation history yet.[/muted]")
        return

    console.print()
    for entry in _history:
        if entry["role"] == "user":
            console.print(
                Panel(
                    Text(entry["content"], style="white"),
                    title="[user]  You[/user]",
                    title_align="right",
                    border_style="cyan",
                    padding=(0, 2),
                    box=box.ROUNDED,
                )
            )
        else:
            console.print(
                Panel(
                    Markdown(entry["content"]),
                    title="[agent]  Advisor[/agent]",
                    border_style="white",
                    padding=(1, 2),
                    box=box.ROUNDED,
                )
            )
        console.print()


# ─── Boot sequence ────────────────────────────────────────────────────────────

def boot_rag() -> TyreRAG:
    """Initialise TyreRAG with a Rich progress display."""
    console.print()
    with Progress(
        SpinnerColumn(spinner_name="dots", style="white"),
        TextColumn("[step]{task.description}[/step]"),
        BarColumn(bar_width=28, style="dim", complete_style="white"),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        t1 = progress.add_task("Loading Excel data…",          total=3)
        t2 = progress.add_task("Building vector index…",        total=3, start=False)
        t3 = progress.add_task("Connecting to Claude API…",     total=3, start=False)

        rag = TyreRAG(quiet=True)

        # Simulate step completion with brief delays for visual feedback
        for _ in range(3):
            progress.advance(t1)
            time.sleep(0.08)

        progress.start_task(t2)
        for _ in range(3):
            progress.advance(t2)
            time.sleep(0.08)

        progress.start_task(t3)
        for _ in range(3):
            progress.advance(t3)
            time.sleep(0.06)

    console.print(
        f"[step.ok]✓[/step.ok] [muted]Ready — "
        f"{rag.record_count} records indexed[/muted]"
    )
    console.print()
    return rag


# ─── Brand / model detection ─────────────────────────────────────────────────

_STOP_WORDS = {
    "what", "is", "the", "tyre", "tyres", "for", "my", "a", "an", "i",
    "have", "need", "want", "recommend", "best", "which", "get", "use",
    "should", "fit", "fits", "on", "of", "give", "tell", "me", "about",
}


def _match_brand(query: str, brands: List[str]) -> Optional[str]:
    """
    Return the longest brand whose name appears as a whole word in the query.
    Uses word-boundary regex to avoid 'RE' matching inside 'tyre'.
    """
    q = query.lower()
    for brand in sorted(brands, key=len, reverse=True):
        pattern = r"\b" + re.escape(brand.lower()) + r"\b"
        if re.search(pattern, q):
            return brand
    return None


def _match_model(query: str, models: List[str]) -> Optional[str]:
    """Return the longest model whose name appears as whole words in the query."""
    q = query.lower()
    for model in sorted(models, key=len, reverse=True):
        pattern = r"\b" + re.escape(model.lower()) + r"\b"
        if re.search(pattern, q):
            return model
    return None


def _find_partial_model_matches(query: str, rag: TyreRAG) -> List[dict]:
    """
    Search every brand's models for any meaningful word in the query.
    Returns list of {"brand": ..., "model": ...} sorted by brand then model.
    E.g. query="pulsar" → [{"brand":"Bajaj","model":"Pulsar"},
                            {"brand":"Bajaj","model":"Pulsar NS"}, ...]
    """
    words = [
        w.strip("?.,!").lower()
        for w in query.split()
        if len(w.strip("?.,!")) > 2 and w.strip("?.,!").lower() not in _STOP_WORDS
    ]
    if not words:
        return []

    results = []
    seen: set = set()
    for brand in rag.get_brands():
        for model in rag.get_models(brand):
            ml = model.lower()
            if any(re.search(r"\b" + re.escape(w) + r"\b", ml) for w in words):
                key = (brand, model)
                if key not in seen:
                    seen.add(key)
                    results.append({"brand": brand, "model": model})
    return results


def _resolve_selection(raw: str, items: List[dict]) -> Optional[dict]:
    """
    Interpret user reply to a disambiguation menu.
    `items` is a list of {"brand":…,"model":…}.
    Accepts a number ("3") or a partial model/brand name.
    """
    raw = raw.strip()
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(items):
            return items[idx]
    # Partial text match
    rl = raw.lower()
    for item in items:
        if rl in item["model"].lower() or rl in item["brand"].lower():
            return item
    return None


def print_disambiguation_menu(matches: List[dict], keyword: str):
    """Print a numbered menu of brand+model matches for an ambiguous keyword."""
    table = Table(
        box=box.SIMPLE,
        show_header=False,
        border_style="dim",
        pad_edge=True,
        show_edge=False,
    )
    table.add_column("#",     style="dim",   width=4, justify="right")
    table.add_column("Brand", style="dim white", width=18)
    table.add_column("Model", style="white", min_width=20)

    for i, m in enumerate(matches, 1):
        table.add_row(str(i), m["brand"], m["model"])

    console.print()
    console.print(
        Panel(
            table,
            title=f"[agent]  Models matching '{keyword}'[/agent]",
            border_style="dim",
            padding=(0, 1),
            box=box.ROUNDED,
        )
    )
    console.print(
        "  [muted]Type a number or include the variant "
        "(e.g. [italic]Pulsar NS 200[/italic])[/muted]"
    )
    console.print()


def print_model_menu(brand: str, models: List[str]):
    """Print a numbered model selection menu for a single brand."""
    table = Table(
        box=box.SIMPLE,
        show_header=False,
        border_style="dim",
        pad_edge=True,
        show_edge=False,
    )
    table.add_column("#",     style="dim",   width=4, justify="right")
    table.add_column("Model", style="white", min_width=24)

    for i, model in enumerate(models, 1):
        table.add_row(str(i), model)

    console.print()
    console.print(
        Panel(
            table,
            title=f"[agent]  {brand} models[/agent]",
            border_style="dim",
            padding=(0, 1),
            box=box.ROUNDED,
        )
    )
    console.print(
        "  [muted]Type a model name or number  ·  include variant for best results "
        "(e.g. [italic]Pulsar NS 200[/italic])[/muted]"
    )
    console.print()


# ─── Query pipeline ───────────────────────────────────────────────────────────

def _step(icon: str, label: str, style: str = "step"):
    console.print(f"  [{style}]{icon}  {label}[/{style}]")


def run_query(rag: TyreRAG, query: str, engine_history: List[dict]) -> str:
    global _last_sources

    sources = rag.retrieve(query, history=engine_history)
    _last_sources = sources
    console.print()

    buffer = ""
    with Live(
        Panel(
            Text("", style="dim white"),
            title="[agent]  Advisor[/agent]",
            border_style="dim",
            padding=(1, 2),
            box=box.ROUNDED,
        ),
        console=console,
        refresh_per_second=20,
        vertical_overflow="visible",
        transient=True,
    ) as live:
        for token in rag.recommend_stream_from_context(query, sources, history=engine_history):
            buffer += token
            live.update(
                Panel(
                    Markdown(buffer),
                    title="[agent]  Advisor[/agent]  [muted]●[/muted]",
                    border_style="dim",
                    padding=(1, 2),
                    box=box.ROUNDED,
                )
            )

    # Print single clean final panel
    console.print(
        Panel(
            Markdown(buffer),
            title="[agent]  Advisor[/agent]",
            border_style="white",
            padding=(1, 2),
            box=box.ROUNDED,
        )
    )
    console.print()
    return buffer


# ─── Command dispatcher ───────────────────────────────────────────────────────

def handle_command(cmd: str, rag: TyreRAG) -> bool:
    """
    Handle slash commands. Returns True to continue the loop, False to exit.
    """
    tok = cmd.strip().lower().split()[0]

    if tok in ("/quit", "/exit", "/q"):
        return False

    elif tok == "/help":
        console.print(
            Panel(
                Markdown(HELP_TEXT),
                title="[cmd]  Help[/cmd]",
                border_style="magenta",
                padding=(1, 2),
                box=box.ROUNDED,
            )
        )
        console.print()

    elif tok == "/clear":
        global _history, _engine_history, _last_sources
        _history = []
        _engine_history = []
        _last_sources = []
        console.clear()
        print_logo()
        print_banner(rag.record_count)

    elif tok == "/history":
        print_history()

    elif tok == "/sources":
        print_sources(_last_sources)

    else:
        console.print(
            f"[error]Unknown command:[/error] [cmd]{tok}[/cmd]  "
            "(type [cmd]/help[/cmd] for available commands)"
        )
        console.print()

    return True


# ─── Main agent loop ──────────────────────────────────────────────────────────

def _agent_loop(rag: TyreRAG):
    print_rule("session started")
    print_examples()

    brands = rag.get_brands()

    # Pending-disambiguation state
    pending_items: List[dict] = []   # {"brand":…,"model":…} list shown to user
    pending_label: str = ""          # keyword shown in prompt while waiting

    while True:
        try:
            prompt_label = (
                f"[user]›  {pending_label}[/user]" if pending_label
                else "[user]›[/user]"
            )
            raw = Prompt.ask(prompt_label, console=console).strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            console.print("[muted]Goodbye![/muted]")
            break

        if not raw:
            continue

        # Slash command — clears any pending state
        if raw.startswith("/"):
            pending_items = []
            pending_label = ""
            if not handle_command(raw, rag):
                console.print("[muted]Goodbye![/muted]")
                break
            continue

        # ── Resolve a pending brand→model selection ─────────────────────
        if pending_items:
            chosen = _resolve_selection(raw, pending_items)
            query = f"{chosen['brand']} {chosen['model']}" if chosen else raw
            pending_items = []
            pending_label = ""

        # ── Fresh input ──────────────────────────────────────────────────
        else:
            matched_brand = _match_brand(raw, brands)
            if matched_brand:
                models = rag.get_models(matched_brand)
                matched_model = _match_model(raw, models)
                if not matched_model:
                    # Pure brand with no model — ask which vehicle
                    items = [{"brand": matched_brand, "model": m} for m in models]
                    pending_items = items
                    pending_label = matched_brand
                    print_model_menu(matched_brand, models)
                    continue
            # Everything else (model name, partial query, full query) → RAG
            query = raw

        _history.append({"role": "user", "content": query})
        try:
            answer = run_query(rag, query, engine_history=list(_engine_history))
            _history.append({"role": "agent", "content": answer})
            # Append this turn to engine history AFTER the call so the model
            # doesn't see the current query in its own "history" list
            _engine_history.append({"role": "user",      "content": query})
            _engine_history.append({"role": "assistant", "content": answer})
        except Exception as e:
            console.print(f"[error]Error:[/error] {e}")
            console.print()

        print_rule()


# ─── CLI commands ─────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def default(ctx: typer.Context):
    """Default: start interactive agent session when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        chat()


@app.command()
def chat():
    """Start an interactive CEAT tyre agent session."""
    print_logo()

    try:
        rag = boot_rag()
    except EnvironmentError as e:
        console.print(f"[error]Error:[/error] {e}")
        raise typer.Exit(1)
    except FileNotFoundError as e:
        console.print(f"[error]Data file not found:[/error] {e}")
        raise typer.Exit(1)

    print_banner(rag.record_count)
    _agent_loop(rag)


@app.command()
def ask(query: str = typer.Argument(..., help="Tyre query to run, then exit")):
    """Run a single query and exit."""
    try:
        rag = boot_rag()
    except EnvironmentError as e:
        console.print(f"[error]Error:[/error] {e}")
        raise typer.Exit(1)

    try:
        run_query(rag, query, engine_history=[])
    except Exception as e:
        console.print(f"[error]Error:[/error] {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
