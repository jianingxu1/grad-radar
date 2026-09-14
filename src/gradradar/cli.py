import argparse

from gradradar.bootstrap import bootstrap_sources
from gradradar.db import create_session_factory, transaction
from gradradar.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("bootstrap-sources", "ingest"))
    command = parser.parse_args().command
    session_factory = create_session_factory(get_settings())
    with transaction(session_factory) as session:
        created = bootstrap_sources(session)
    print(f"{command}: bootstrapped sources (created={created})")


if __name__ == "__main__":
    main()
