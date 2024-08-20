import os

from loguru import logger


def export_results(results: list[tuple[str, str, bool]], module: str) -> None:
    if not os.path.exists("./results"):
        os.makedirs("./results")

    if module == "register":
        success_txt = open("./results/registration_success.txt", "w")
        failed_txt = open("./results/registration_failed.txt", "w")

        for email, password, status in results:
            if status:
                success_txt.write(f"{email}:{password}\n")
            else:
                failed_txt.write(f"{email}:{password}\n")

    elif module == "export_wallets":
        success_txt = open("./results/wallets_exported.txt", "w")
        failed_txt = open("./results/wallets_failed.txt", "w")

        for email, wallet in results:
            if wallet:
                success_txt.write(f"{email}:{wallet}\n")
            else:
                failed_txt.write(f"{email}\n")

    logger.debug("Results exported to results folder")
