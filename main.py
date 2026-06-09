#!/usr/bin/env python3
"""
Agent-7 — Your AI System Automation Powerhouse
=================================================
An autonomous AI agent that controls your Mac like a human.
Tell it what to do in plain English, and it does it.

Usage:
    python3 main.py                  # Start interactive mode
    python3 main.py "open chrome"    # Execute a single command
    python3 main.py --dashboard      # Start with web dashboard
"""

import sys
import asyncio
import argparse
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

from config import Config

console = Console()


# ── Styled Output ─────────────────────────────────────────────

BANNER = """
[bold cyan]
    █████╗  ██████╗ ███████╗███╗   ██╗████████╗     ███████╗
   ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝     ╚════██║
   ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   █████╗    ██╔╝
   ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ╚════╝   ██╔╝ 
   ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║            ██╔╝  
   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝            ╚═╝   
[/bold cyan]
[bold white]   ⚡ Advanced AI System Automation — v2.0[/bold white]
[dim]   Powered by Google Gemini • Full Computer Control[/dim]
"""


def print_status(message: str):
    """Callback for status updates from the executor."""
    console.print(f"  {message}")


def print_action(action: dict):
    """Callback for action notifications from the executor."""
    pass  # Status callback handles display


def show_welcome():
    """Display the welcome screen."""
    console.print(BANNER)

    issues = Config.validate()
    if issues:
        console.print(Panel(
            "\n".join(f"[red]✗[/red] {issue}" for issue in issues),
            title="[bold red]⚠️  Configuration Issues[/bold red]",
            border_style="red",
            box=box.ROUNDED,
        ))
        return False
    else:
        screen_w, screen_h = Config.get_screen_size()
        console.print(Panel(
            "[green]✓[/green] Gemini API key configured\n"
            f"[green]✓[/green] Vision model: {Config.VISION_MODEL}\n"
            f"[green]✓[/green] Smart model: {Config.SMART_MODEL}\n"
            f"[green]✓[/green] Confirmation: {Config.CONFIRMATION_LEVEL}\n"
            f"[green]✓[/green] Kill switch: {'Enabled' if Config.KILL_SWITCH_ENABLED else 'Disabled'}\n"
            f"[green]✓[/green] Screen: {screen_w}x{screen_h}",
            title="[bold green]✅ Agent-7 Ready[/bold green]",
            border_style="green",
            box=box.ROUNDED,
        ))
        return True


def show_help():
    """Display help information."""
    table = Table(
        title="🤖 Agent-7 Command Guide",
        box=box.ROUNDED,
        border_style="cyan",
    )
    table.add_column("Command", style="bold cyan", min_width=35)
    table.add_column("Description", style="white")

    commands = [
        ("📝 Any plain English instruction", "Agent will plan and execute it"),
        ("", ""),
        ("[bold]── Examples ─────────────────────[/bold]", ""),
        ("'Open WhatsApp and message John'", "Browser + messaging automation"),
        ("'Post photos to Instagram'", "Image upload with AI captions"),
        ("'Open Terminal and run ls -la'", "System + terminal control"),
        ("'Search Google for weather'", "Browser automation"),
        ("'Open Finder and create a new folder'", "File management"),
        ("'Take a screenshot and describe it'", "Vision + analysis"),
        ("", ""),
        ("[bold]── Special Commands ─────────────[/bold]", ""),
        ("help", "Show this help message"),
        ("status", "Show agent status and task history"),
        ("stop", "Stop the current task"),
        ("clear", "Clear screen"),
        ("quit / exit", "Exit Agent-7"),
    ]

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    console.print(table)
    console.print()
    console.print(
        "[dim]💡 Tips:\n"
        "  • Move mouse to screen corner → emergency stop\n"
        "  • Agent sees your screen in real-time via screenshots\n"
        "  • Complex tasks are auto-decomposed into steps\n"
        "  • If stuck, the agent will try alternative approaches[/dim]"
    )


async def interactive_mode(executor):
    """Run the interactive CLI loop."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

    history_file = Config.LOGS_DIR / ".command_history"
    session = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
    )

    console.print(
        "\n[bold]Type any command in plain English. Type 'help' for options.[/bold]\n"
    )

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.prompt("🤖 You: ", multiline=False)
            )
            user_input = user_input.strip()

            if not user_input:
                continue

            # Handle special commands
            match user_input.lower():
                case "quit" | "exit" | "q":
                    console.print(
                        "\n[bold cyan]👋 Goodbye! Agent-7 shutting down...[/bold cyan]"
                    )
                    await executor.cleanup()
                    break

                case "help" | "h" | "?":
                    show_help()
                    continue

                case "clear" | "cls":
                    console.clear()
                    continue

                case "status":
                    summary = executor.memory.get_task_summary()
                    console.print(Panel(
                        summary,
                        title="Agent Status",
                        border_style="blue",
                    ))
                    continue

                case "stop":
                    executor.stop()
                    continue

                case _:
                    pass

            # Display task
            console.print()
            console.print(Panel(
                f"[bold]{user_input}[/bold]",
                title="[cyan]📋 Task[/cyan]",
                border_style="cyan",
                box=box.ROUNDED,
            ))

            # Execute the command
            start_time = datetime.now()
            result = await executor.execute_command(user_input)
            elapsed = (datetime.now() - start_time).total_seconds()

            # Show result
            status_color = "green" if result["status"] == "completed" else "red"
            console.print(Panel(
                f"[{status_color}]{result['message']}[/{status_color}]\n"
                f"[dim]Time: {elapsed:.1f}s | "
                f"Actions: {result.get('actions_taken', '?')}[/dim]",
                title=f"[{status_color}]Result[/{status_color}]",
                border_style=status_color,
                box=box.ROUNDED,
            ))
            console.print()

        except KeyboardInterrupt:
            console.print(
                "\n[yellow]Use 'quit' to exit, or Ctrl+C again to force quit.[/yellow]"
            )
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input()
                )
            except KeyboardInterrupt:
                console.print("\n[bold red]Force quitting...[/bold red]")
                await executor.cleanup()
                break

        except EOFError:
            console.print("\n[bold cyan]👋 Goodbye![/bold cyan]")
            await executor.cleanup()
            break

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


async def single_command_mode(executor, command: str):
    """Execute a single command and exit."""
    console.print(Panel(
        f"[bold]{command}[/bold]",
        title="[cyan]📋 Executing[/cyan]",
        border_style="cyan",
    ))

    start_time = datetime.now()
    result = await executor.execute_command(command)
    elapsed = (datetime.now() - start_time).total_seconds()

    status_color = "green" if result["status"] == "completed" else "red"
    console.print(Panel(
        f"[{status_color}]{result['message']}[/{status_color}]\n"
        f"[dim]Time: {elapsed:.1f}s[/dim]",
        title=f"[{status_color}]Result[/{status_color}]",
        border_style=status_color,
    ))

    await executor.cleanup()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Agent-7 — AI System Automation Powerhouse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py                           # Interactive mode
  python3 main.py "open Google Chrome"      # Single command
  python3 main.py "post photos to insta"    # Automated posting
  python3 main.py --dashboard               # With web dashboard
        """,
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="Command to execute (omit for interactive mode)",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Start with web monitoring dashboard",
    )
    parser.add_argument(
        "--mcq",
        action="store_true",
        help="Start in lightweight MCQ-only mode",
    )

    args = parser.parse_args()

    # Show welcome
    if not show_welcome():
        console.print(
            "\n[bold yellow]Please fix the configuration issues above.[/bold yellow]"
        )
        console.print(
            "1. Copy .env.example to .env: [cyan]cp .env.example .env[/cyan]\n"
            "2. Add your Gemini API key to .env\n"
            "3. Get a key at: [link]https://aistudio.google.com[/link]"
        )
        sys.exit(1)

    # If MCQ-only mode requested, bypass normal executor startup
    if args.mcq:
        from agent.brain import GeminiBrain
        from controllers.screen import ScreenController
        from controllers.mouse import MouseController
        from agent.mcq_solver import MCQSolver

        console.print("[bold yellow]⚡ Initializing lightweight MCQ Solver...[/bold yellow]")
        brain = GeminiBrain()
        screen = ScreenController()
        mouse = MouseController()

        mcq_solver = MCQSolver(brain=brain, screen=screen, mouse=mouse)
        mcq_solver.start_listener()

        console.print("[bold green]MCQ Solver running in background. Use hotkeys: [/bold green]")
        console.print("[cyan]  Control + Command[/cyan]  -> Solve & auto-click")
        console.print("[magenta]  Control + Option[/magenta]   -> Just show answer in overlay/notification")
        console.print("[bold yellow]Press Ctrl+C to exit.[/bold yellow]\n")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[bold red]Shutting down MCQ Solver...[/bold red]")
        sys.exit(0)

    # Initialize the executor
    from agent.executor import AgentExecutor
    executor = AgentExecutor(
        on_status=print_status,
        on_action=print_action,
    )

    # Initialize and start MCQ Solver
    from agent.mcq_solver import MCQSolver
    mcq_solver = MCQSolver(brain=executor.brain, screen=executor.screen, mouse=executor.mouse)
    mcq_solver.start_listener()

    # Start dashboard if requested
    if args.dashboard:
        console.print(
            f"\n[green]🖥️  Dashboard: http://localhost:{Config.DASHBOARD_PORT}[/green]"
        )
        try:
            from dashboard.app import start_dashboard_background
            start_dashboard_background(executor)
        except ImportError:
            console.print(
                "[yellow]Dashboard not available. Continuing without it.[/yellow]"
            )

    # Execute
    if args.command:
        await single_command_mode(executor, args.command)
    else:
        await interactive_mode(executor)


if __name__ == "__main__":
    asyncio.run(main())
