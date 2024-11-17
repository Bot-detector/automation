import logging
import os
from datetime import date

import requests
from discord import File, SyncWebhook

from config import config

from . import functions

logger = logging.getLogger(__name__)


def make_folder() -> None:
    try:
        os.mkdir("Reports/")
    except FileExistsError as e:
        logger.error(str(e))
    return


def call_webhook(path: str, url: str) -> None:
    logger.debug("sending webhook")
    webhook = SyncWebhook.from_url(url, session=requests.Session())
    file = File(path)
    webhook.send(content="<@&893399220172767253>", file=file)
    return


def tipoff_bots() -> None:
    logger.info("Crafting Tipoff")

    make_folder()

    df = functions.get_tipoff_data()
    today_ISO = date.today().isoformat()
    dataframe_length = len(df.index)

    if dataframe_length < 1:
        logger.debug(f"dataframe is to small: #{dataframe_length}")
        return

    REPORT_NAME = f"BDP-{today_ISO}-{dataframe_length}"
    REPORT_FILE_NAME = REPORT_NAME + ".csv"

    df.to_csv(f"Reports\\{REPORT_FILE_NAME}", index=False)
    PATH_TO_CSV_FILE = f"Reports\\{REPORT_FILE_NAME}"

    MESSAGE_BODY = f"Bot Detector Plugin Report for {today_ISO}."
    EMAIL_SUBJECT = f"{REPORT_NAME} | " + config.JMOD_TAG

    functions.send_tipoff(
        MESSAGE_BODY=MESSAGE_BODY,
        EMAIL_SUBJECT=EMAIL_SUBJECT,
        PATH_TO_CSV_FILE=PATH_TO_CSV_FILE,
        FILE_NAME=REPORT_FILE_NAME,
    )

    call_webhook(path=PATH_TO_CSV_FILE, url=config.PATRON_WEBHOOK)
    return
