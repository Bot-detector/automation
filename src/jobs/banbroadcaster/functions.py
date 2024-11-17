import logging
import operator
import time
from collections import namedtuple

# from datetime import datetime
from typing import List

import mysql.connector

# import tweepy
from discord_webhook import DiscordWebhook
from discord_webhook.webhook import DiscordEmbed

from config import config

from . import queries

logger = logging.getLogger(__name__)

# AUTH = tweepy.OAuthHandler(
#     consumer_key=config.CONSUMER_KEY, consumer_secret=config.CONSUMER_SECRET
# )
# AUTH.set_access_token(key=config.ACCESS_TOKEN, secret=config.ACCESS_TOKEN_SECRET)
# TWITTER_API = tweepy.API(AUTH, wait_on_rate_limit=True)


config_players = {
    "user": config.SERVER_LOGIN,
    "password": config.SERVER_PASSWORD,
    "host": config.SERVER_ADDRESS,
    "database": config.DATABASE,
}


def execute_sql(sql: str, insert: bool = False, param: dict = None):
    conn = mysql.connector.connect(**config_players)
    mycursor = conn.cursor(buffered=True, dictionary=True)

    mycursor.execute(sql, param)

    if insert:
        conn.commit()
        mycursor.close()
        conn.close()
        return

    rows = mycursor.fetchall()
    Record = namedtuple("Record", rows[0].keys())
    records = [Record(*r.values()) for r in rows]

    mycursor.close()
    conn.close()
    return records


def get_ban_counts():
    total_pending_bans = execute_sql(sql=queries.sql_get_count_banned_players)[0].bans
    real_player_bans = execute_sql(sql=queries.sql_get_count_banned_real_players)[
        0
    ].real_bans
    no_data_bans = execute_sql(sql=queries.sql_get_count_banned_no_data)[0].no_data_bans

    try:
        bot_records = execute_sql(sql=queries.sql_get_banned_bots_names)
        banned_bot_names = [record.name for record in bot_records]
        banned_bot_predictions = [record.prediction for record in bot_records]
    except IndexError as e:
        logger.error(str(e))
        banned_bot_names = []
        banned_bot_predictions = []

    return (
        total_pending_bans,
        real_player_bans,
        no_data_bans,
        banned_bot_names,
        banned_bot_predictions,
    )


def apply_bot_bans():
    execute_sql(sql=queries.sql_apply_bot_bans, insert=True)
    return


def broadcast_bans_complete(num_bans: int):
    if num_bans > 0:
        embed = DiscordEmbed(
            title="Bans Added!",
            color="000000",
            description="Bans were added to the project's total. Time to check your kc! ",
        )
        embed.set_timestamp()
        embed.add_embed_field(
            name="Total Bans Added:", value=f"{num_bans:,}", inline=False
        )
        embed.set_thumbnail(
            url="https://oldschool.runescape.wiki/images/5/58/Crazy_dance.gif"
        )
        webhook = DiscordWebhook(url=config.GRAVEYARD_WEBHOOK, rate_limit_retry=True)
        webhook.add_embed(embed=embed)
        webhook.execute()

        webhook = DiscordWebhook(
            url=config.GRAVEYARD_WEBHOOK,
            rate_limit_retry=True,
            content="<@&893399220172767253>",
        )
        webhook.execute()


def broadcast_totals(
    total_bans: int, real_player_bans: int, no_data_bans: int, bot_bans: int
):
    embed = DiscordEmbed(
        title="Pending Bans Stats",
        color="000000",
        description="Latest Ban Totals From Our Hiscores Scrapes",
    )
    embed.set_timestamp()
    embed.add_embed_field(
        name="Total Unapplied Bans", value=f"{total_bans:,}", inline=False
    )
    embed.add_embed_field(
        name="Predicted as Real Player (Not Counted)",
        value=f"{real_player_bans:,}",
        inline=False,
    )
    embed.add_embed_field(
        name="No Hiscore Data (Not Counted)", value=f"{no_data_bans:,}", inline=False
    )
    embed.add_embed_field(
        name="Predicted as Bots (These Count)", value=f"{bot_bans:,}", inline=False
    )
    embed.set_thumbnail(url="https://c.tenor.com/V71SmWqyYHkAAAAM/kermit-freaking.gif")

    webhook = DiscordWebhook(url=config.GRAVEYARD_WEBHOOK, rate_limit_retry=True)
    webhook.add_embed(embed=embed)
    webhook.execute()


def broadcast_names(names_list: List[str]):
    logger.debug("Broadcasting Names")
    while True:
        num_pending_players = len(names_list)
        # if is empty list break
        if not names_list:
            break
        elif num_pending_players > 50:
            broadcast_size = 50
        else:
            broadcast_size = num_pending_players
        players_to_broadcast = []

        for i in range(broadcast_size):
            players_to_broadcast.append(names_list.pop())

        embed = DiscordEmbed(
            title="All Ye Bots Lose All Hope!",
            color="000000",
            description=f"{broadcast_size} Accounts",
        )
        embed.set_timestamp()
        embed.add_embed_field(
            name="Bans Being Added", value=f"{', '.join(players_to_broadcast)}"
        )
        embed.set_thumbnail(url="https://i.imgur.com/PPnZRHW.gif")

        webhook = DiscordWebhook(url=config.GRAVEYARD_WEBHOOK)
        webhook.add_embed(embed=embed)

        try:
            webhook.execute()
        except Exception:
            pass
        time.sleep(5)


# def post_bans_tweet(num_bans: int):
#     logger.debug("Posting Ban Tweet")
#     msg = f"BANS ALERT - {datetime.now().strftime('%d-%m-%Y')}: {num_bans:,d} accounts our system has detected as bots have been banned in the past 24 hours."
#     TWITTER_API.update_status(msg)


# def post_breakdown_tweets(predictions: List[str]):
#     logger.debug("Posting Breakdown Tweet")
#     tweets = generate_breakdown_tweets(predictions)

#     if len(tweets) == 0:
#         return

#     previous_status = None

#     for i, tweet in enumerate(tweets):
#         tweet += f"({i+1}/{len(tweets)})"

#         if i == 0:
#             previous_status = TWITTER_API.update_status(tweet)
#         else:
#             previous_status = TWITTER_API.update_status(
#                 tweet, in_reply_to_status_id=previous_status.id
#             )

#         time.sleep(3)

#     return


# def generate_breakdown_tweets(predictions: List[str]):
#     logger.info("Generating Breakdown Tweet")
#     predictions_groupings = group_predictions(predictions)

#     tweets = []

#     current_tweet = "Bans by Category:\n"

#     for pred, count in predictions_groupings.items():
#         pred_string = f"{pred}: {count}\n"

#         if (len(current_tweet) + len(pred_string)) >= 240:
#             tweets.append(current_tweet)
#             current_tweet = pred_string
#         else:
#             current_tweet += pred_string

#     # Grab the leftovers!
#     tweets.append(current_tweet)

#     return tweets


def group_predictions(predictions: List[str]):
    logger.debug("Grouping Predictions")
    grouped = {}

    for p in predictions:
        if p.lower() == "real_player" or p.lower() == "stats too low":
            current_pred = "Toss up (Didn't last long)"
        else:
            current_pred = p.replace("_", " ")

        group = grouped.get(current_pred)

        if group is None:
            grouped[current_pred] = 1
        else:
            grouped[current_pred] += 1

    return dict(sorted(grouped.items(), key=operator.itemgetter(1), reverse=True))
