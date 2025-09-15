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
        "🆕 Register accounts",
        "🔍 Verify accounts",
        "🔑 Login accounts",
        "🌾 Farm accounts",
        "✅ Complete tasks",
        "📊 Export accounts statistics",
        "",
        "🧹 Clean accounts proxies",
        "❌ Exit",
    )
    MODULES_DATA = {
        "🆕 Register accounts": "registration",
        "🔍 Verify accounts": "verify",
        "🔑 Login accounts": "login",
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

        version = Text("VERSION: 2.3", style="blue")
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

        # Application Settings
        app_settings_table = Table(box=box.SIMPLE)
        app_settings_table.add_column("Parameter", style="cyan")
        app_settings_table.add_column("Value", style="magenta")
        app_settings_table.add_row("Threads", str(config.application_settings.threads))
        app_settings_table.add_row("Keepalive Interval", str(config.application_settings.keepalive_interval) + " sec")
        app_settings_table.add_row("Database URL", config.application_settings.database_url)
        app_settings_table.add_row("Skip Logged Accounts", str(config.application_settings.skip_logged_accounts))
        app_settings_table.add_row("Shuffle Accounts", str(config.application_settings.shuffle_accounts))

        # Captcha Settings
        captcha_settings_table = Table(box=box.SIMPLE)
        captcha_settings_table.add_column("Parameter", style="cyan")
        captcha_settings_table.add_column("Value", style="magenta")
        captcha_settings_table.add_row("Captcha Service", config.captcha_settings.captcha_service)
        captcha_settings_table.add_row("Max Captcha Solving Time", str(config.captcha_settings.max_captcha_solving_time) + " sec")

        # Redirect Settings
        redirect_settings_table = Table(box=box.SIMPLE)
        redirect_settings_table.add_column("Parameter", style="cyan")
        redirect_settings_table.add_column("Value", style="magenta")
        redirect_settings_table.add_row("Enable", str(config.redirect_settings.enabled))
        redirect_settings_table.add_row("Email", config.redirect_settings.email)
        redirect_settings_table.add_row("IMAP Server", config.redirect_settings.imap_server)

        # IMAP Settings
        imap_settings_table = Table(box=box.SIMPLE)
        imap_settings_table.add_column("Parameter", style="cyan")
        imap_settings_table.add_column("Value", style="magenta")
        imap_settings_table.add_row("Use Proxy for IMAP", str(config.imap_settings.use_proxy_for_imap))
        imap_settings_table.add_row("Use Single IMAP", str(config.imap_settings.use_single_imap.enable))
        imap_settings_table.add_row("Single IMAP Server", config.imap_settings.use_single_imap.imap_server)

        # Accounts Table
        accounts_table = Table(box=box.SIMPLE)
        accounts_table.add_column("Parameter", style="cyan")
        accounts_table.add_column("Value", style="magenta")

        accounts_table.add_row("Accounts to register", str(len(config.accounts_to_register)))
        accounts_table.add_row("Accounts to farm", str(len(config.accounts_to_farm)))
        accounts_table.add_row("Accounts to login", str(len(config.accounts_to_login)))
        accounts_table.add_row("Accounts to export stats", str(len(config.accounts_to_export_stats)))
        accounts_table.add_row("Account to complete tasks", str(len(config.accounts_to_complete_tasks)))
        accounts_table.add_row("Referral codes", str(len(config.referral_codes)))
        accounts_table.add_row("Proxies", str(len(config.proxies)))

        # Add all tables to the main table
        main_table.add_column("Section")
        main_table.add_row("[bold]Application Settings[/bold]", app_settings_table)
        main_table.add_row("[bold]Captcha Settings[/bold]", captcha_settings_table)
        main_table.add_row("[bold]Redirect Settings[/bold]", redirect_settings_table)
        main_table.add_row("[bold]IMAP Settings[/bold]", imap_settings_table)
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
