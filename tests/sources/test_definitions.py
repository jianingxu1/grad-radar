from app.sources.definitions import SOURCES, SourceName


def test_source_definitions_have_unique_names() -> None:
    assert {source.name for source in SOURCES} == {SourceName.SIMPLIFY, SourceName.SPEEDYAPPLY}
    assert len({source.priority for source in SOURCES}) == len(SOURCES)
