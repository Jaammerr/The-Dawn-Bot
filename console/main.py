import os
import sys
import inquirer

from inquirer.themes import GreenPassion
from art import tprint

from colorama import Fore
from loader import config
from .logger import info_log

sys.path.append(os.path.realpath("."))


class Console:
    MODULES = (
        "Register",
        "Farm (cycle)",
        # "Farm (one time)",
        "Complete tasks",
        # "Export wallets",
        "Exit",
    )
    MODULES_DATA = {
        "Register": "register",
        "Farm (cycle)": "farm_cycle",
        "Farm (one time)": "farm_one_time",
        "Complete tasks": "complete_tasks",
        "Export wallets": "export_wallets",
    }

    @staticmethod
    def show_dev_info():
        os.system("cls")
        tprint("JamBit")
        print("\033[36m" + "VERSION: " + "\033[34m" + "1.3" + "\033[34m")
        print(
            "\033[36m" + "Channel: " + "\033[34m" + "https://t.me/JamBitPY" + "\033[34m"
        )
        print(
            "\033[36m"
            + "GitHub: "
            + "\033[34m"
            + "https://github.com/Jaammerr"
            + "\033[34m"
        )
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

    def build(self) -> None:
        os.system("cls")
        self.show_dev_info()
        info_log(
            f"\n- Accounts to register: {len(config.accounts_to_register)}\n- Accounts to farm: {len(config.accounts_to_farm)}\n- Threads: {config.threads}\n"
        )

        module = self.get_module()
        if module == "Exit":
            exit(0)

        config.module = self.MODULES_DATA[module]
