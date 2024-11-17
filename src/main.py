import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-broadcast",
        action="store_true",
    )
    parser.add_argument(
        "--run-tipoff",
        action="store_true",
    )
    parser.add_argument(
        "--run-kafka",
        action="store_true",
    )

    args = parser.parse_args()

    if args.run_broadcast:
        from jobs.banbroadcaster.main import broadcast_bans

        broadcast_bans()
    elif args.run_tipoff:
        from jobs.tipoff.main import tipoff_bots

        tipoff_bots()
    elif args.run_kafka:
        from jobs.kafka.players.main import get_players_to_scrape

        get_players_to_scrape()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
