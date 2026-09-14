import argparse

from gradradar.config.settings import get_settings
from gradradar.database.session import create_session_factory, transaction
from gradradar.services.github_ingestion import ingest_all
from gradradar.sources.bootstrap import bootstrap_sources


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("bootstrap-sources", "ingest"))
    command = parser.parse_args().command
    session_factory = create_session_factory(get_settings())
    if command == "ingest":
        summaries = ingest_all(session_factory, get_settings().github_token)
        print(*summaries, sep="\n")
        if all(summary.status == "failed" for summary in summaries):
            raise SystemExit(1)
        return
    with transaction(session_factory) as session:
        created = bootstrap_sources(session)
    print(f"bootstrapped sources (created={created})")


if __name__ == "__main__":
    main()
