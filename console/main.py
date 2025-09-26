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
        "🆕 Register & Login accounts",
        "🌾 Farm accounts",
        # "✅ Complete tasks",
        "📊 Export accounts statistics",
        "",
        "🧹 Clean accounts proxies",
        "❌ Exit",
    )
    MODULES_DATA = {
        "🆕 Register & Login accounts": "login",
        "🌾 Farm accounts": "farm",
        "📊 Export accounts statistics": "export_stats",
        "✅ Complete tasks": "complete_tasks",
        "🧹 Clean accounts proxies": "clean_accounts_proxies",
        "❌ Exit": "exit",
    }

    def __init__(self):
        self.rich_console = RichConsole()

    def show_dev_info(self):
        os.system("cls" if os.name == "nt" else "clear")

        title = text2art("JamBit", font="small")
        styled_title = Text(title, style="bold cyan")

        version = Text("VERSION: 3.0", style="blue")
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
        main_table = Table(title="Configuration Overview", box=box.ROUNDED, show_lines=True)

        # Accounts Table
        accounts_table = Table(box=box.SIMPLE)
        accounts_table.add_column("Parameter", style="cyan")
        accounts_table.add_column("Value", style="magenta")

        accounts_table.add_row("Accounts to farm", str(len(config.accounts_to_farm)))
        accounts_table.add_row("Accounts to login", str(len(config.accounts_to_login)))
        accounts_table.add_row("Accounts to export stats", str(len(config.accounts_to_export_stats)))
        # accounts_table.add_row("Account to complete tasks", str(len(config.accounts_to_complete_tasks)))
        accounts_table.add_row("Referral codes", str(len(config.referral_codes)))
        accounts_table.add_row("Proxies", str(len(config.proxies)))

        main_table.add_row("[bold]Files Information[/bold]", accounts_table)

        panel = Panel(
            main_table,
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
