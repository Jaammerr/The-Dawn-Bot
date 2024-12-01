import os
import sys
import inquirer

from inquirer.themes import GreenPassion
from art import text2art
from colorama import Fore
from loader import config

from rich.console import Console as RichConsole
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

sys.path.append(os.path.realpath("."))


class Console:
    MODULES = (
        "Register",
        "Farm",
        "Complete tasks",
        "Re-verify accounts",
        "Export statistics",
        "Exit",
    )
    MODULES_DATA = {
        "Register": "register",
        "Farm": "farm",
        "Exit": "exit",
        "Export statistics": "export_stats",
        "Complete tasks": "complete_tasks",
        "Re-verify accounts": "re_verify_accounts",
    }

    def __init__(self):
        self.rich_console = RichConsole()

    def show_dev_info(self):
        os.system("cls" if os.name == "nt" else "clear")

        title = text2art("JamBit", font="small")
        styled_title = Text(title, style="bold cyan")

        version = Text("VERSION: 1.6", style="blue")
        telegram = Text("Channel: https://t.me/JamBitPY", style="green")
        github = Text("GitHub: https://github.com/Jaammerr", style="green")

        dev_panel = Panel(
            Text.assemble(styled_title, "\n", version, "\n", telegram, "\n", github),
            border_style="yellow",
            expand=False,
            title="[bold green]Welcome[/bold green]",
            subtitle="[italic]Powered by Jammer[/italic]",
        )

        self.rich_console.print(dev_panel)
        print()

    @staticmethod
    def prompt(data: list):
        answers = inquirer.prompt(data, theme=GreenPassion())
        return answers

    def get_module(self):
        questions = [
            inquirer.List(
                "module",
                message=Fore.LIGHTBLACK_EX + "Select the module",
                choices=self.MODULES,
            ),
        ]

        answers = self.prompt(questions)
        return answers.get("module")

    def display_info(self):
        table = Table(title="Dawn Configuration", box=box.ROUNDED)
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="magenta")

        if config.redirect_settings.enabled:
            table.add_row("Redirect mode", "Enabled")
            table.add_row("Redirect email", config.redirect_settings.email)

        table.add_row("Accounts to register", str(len(config.accounts_to_register)))
        table.add_row("Accounts to farm", str(len(config.accounts_to_farm)))
        table.add_row("Accounts to re-verify", str(len(config.accounts_to_reverify)))
        table.add_row("Threads", str(config.threads))
        table.add_row(
            "Delay before start",
            f"{config.delay_before_start.min} - {config.delay_before_start.max} sec",
        )

        panel = Panel(
            table,
            expand=False,
            border_style="green",
            title="[bold yellow]System Information[/bold yellow]",
            subtitle="[italic]Use arrow keys to navigate[/italic]",
        )
        self.rich_console.print(panel)

    def build(self) -> None:
        self.show_dev_info()
        self.display_info()

        module = self.get_module()
        config.module = self.MODULES_DATA[module]

        if config.module == "exit":
            exit(0)
