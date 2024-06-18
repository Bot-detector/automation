import asyncio
import json
import logging
from asyncio import Queue
from datetime import datetime, timedelta
from time import time
from typing import Any

import aiohttp
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from config import config

from .models import Player

logger = logging.getLogger(__name__)
APPCONFIG = config.AppConfig()


async def check_total_consumer_lag(consumer: AIOKafkaConsumer, topic: str):
    total_lag = 0

    # Get the list of partitions for the topic
    partitions = consumer.partitions_for_topic(topic)
    logger.info(f"{partitions=}")
    if partitions is None:
        logger.warning("partitions is none")
        return 0

    for partition in partitions:
        tp = TopicPartition(topic, partition)

        # Get the last offset committed by the consumer
        committed = await consumer.committed(tp)

        # Get the latest offset in the topic
        end_offset = await consumer.end_offsets([tp])

        # Calculate the lag for this partition
        lag = end_offset[tp] - committed

        # Add the lag for this partition to the total lag
        total_lag += lag

    return total_lag


async def kafka_consumer(topic: str, group: str):
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=[APPCONFIG.KAFKA_HOST],
        group_id=group,
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        auto_offset_reset="earliest",
    )
    await consumer.start()
    return consumer


async def kafka_producer():
    producer = AIOKafkaProducer(
        bootstrap_servers=[APPCONFIG.KAFKA_HOST],
        value_serializer=lambda v: json.dumps(v).encode(),
        acks="all",
    )
    await producer.start()
    return producer


async def send_messages(topic: str, producer: AIOKafkaProducer, send_queue: Queue):
    last_interval = time()
    messages_sent = 0

    while True:
        if send_queue.empty():
            await asyncio.sleep(1)
        message: Player = await send_queue.get()
        await producer.send(topic, value=message.dict())
        send_queue.task_done()

        messages_sent += 1

        if messages_sent >= 1000:
            current_time = time()
            elapsed_time = current_time - last_interval
            speed = messages_sent / elapsed_time
            logger.info(
                f"processed {messages_sent} in {elapsed_time:.2f} seconds, {speed:.2f} msg/sec"
            )

            last_interval = time()
            messages_sent = 0


def is_today(updated_at: str):
    if updated_at is None:
        return False
    today = datetime.now().date()
    date = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%S").date()
    return date == today


def in_date_range(date: str, delta_days: int) -> bool:
    """
    Returns true if the given date is between now and delta_days in the past.

    :param date: Date string in the format "%Y-%m-%dT%H:%M:%S".
    :param delta_days: Number of days in the past to include in the range.
    :return: True if the date is within the range, False otherwise.
    """
    if date is None:
        return False

    try:
        _date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S").date()
    except ValueError:
        return False

    today = datetime.now().date()
    date_limit = today - timedelta(days=delta_days)

    return date_limit <= _date <= today


async def parse_data(players: list[dict], delta_days: int) -> tuple[list[Player], int]:
    players: list[Player] = [Player(**player) for player in players]
    max_id = max([p.id for p in players])

    # for player in players:
    #     if not len(player.name) < 13:
    #         logger.debug(f"len({player.name}) is gt than 13")
    #         skip = True
    #     if is_today(player.updated_at):
    #         logger.debug(f"len({player.updated_at}) is today")

    players = [
        player
        for player in players
        if len(player.name) < 13 and not in_date_range(player.updated_at, delta_days)
    ]
    return players, max_id


async def get_request(
    url: str, params: dict, headers: dict = {}
) -> tuple[list[dict], Any]:
    data = None
    error = None
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.ok:
                data = await resp.json()
            else:
                error = {
                    "status": resp.status,
                    "body": await resp.text(),
                    "url": url,
                    "params": params,
                }
                logger.error(error)
    return data, error


async def get_data(receive_queue: Queue, consumer: AIOKafkaConsumer):
    last_day = datetime.now().date()
    max_id = 0
    params = {
        "limit": APPCONFIG.BATCH_SIZE,
        "player_id": max_id,
        "greater_than": 1,
    }
    headers = {"token": APPCONFIG.API_TOKEN}
    url = f"{APPCONFIG.ENDPOINT}/v2/player"

    delta_days = 7
    while True:
        today = datetime.now().date()

        lag = await check_total_consumer_lag(consumer=consumer, topic="player")

        if lag > 100_000:
            logger.info(f"lag is to high: {lag=}")
            await asyncio.sleep(60)
            continue

        players, error = await get_request(url=url, params=params, headers=headers)

        if error is not None:
            sleep_time = 30
            logger.info(f"sleeping {sleep_time}")
            await asyncio.sleep(sleep_time)
            continue

        len_players = len(players)

        players, max_id = await parse_data(players=players, delta_days=delta_days)
        logger.info(
            {
                "received": len_players,
                "parsed": len(players),
                "max_id": {params.get("player_id")},
            }
        )

        await asyncio.gather(*[receive_queue.put(item=p) for p in players])

        if max_id > params["player_id"]:
            params["player_id"] = max_id

        if today != last_day:
            logger.info("New day!, resetting player_id to 0")
            params["player_id"] = 0
            last_day = today

        if len_players < APPCONFIG.BATCH_SIZE and delta_days > 1:
            delta_days = delta_days - 1
            params["player_id"] = 0
            logger.info(f"reducing delta_days to {delta_days} days")
        elif len_players < APPCONFIG.BATCH_SIZE and delta_days <= 1:
            sleep_time = 300
            logger.info(f"Received {len_players}, sleeping: {sleep_time}")
            await asyncio.sleep(sleep_time)


async def main():
    send_queue = Queue()
    receive_queue = Queue()
    producer = await kafka_producer()
    consumer = await kafka_consumer(topic="player", group="scraper")

    asyncio.create_task(get_data(receive_queue=receive_queue, consumer=consumer))
    asyncio.create_task(
        send_messages(topic="player", producer=producer, send_queue=send_queue)
    )

    while True:
        if receive_queue.empty():
            await asyncio.sleep(1)

        message = await receive_queue.get()
        await send_queue.put(message)
        receive_queue.task_done()


def get_players_to_scrape():
    asyncio.ensure_future(main())
