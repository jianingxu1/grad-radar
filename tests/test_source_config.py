from gradradar.source_config import SOURCES


def test_source_definitions_have_unique_names() -> None:
    assert {source.name for source in SOURCES} == {"simplify", "speedyapply"}
    assert len({source.priority for source in SOURCES}) == len(SOURCES)
