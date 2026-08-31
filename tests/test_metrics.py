"""Tests for the declarative metric registry.

The client's metric set changes quarterly, so a metric is a definition rather
than code. That only helps if a bad definition fails loudly: a custom metric
that half-works would put an unlabelled or wrongly-scaled number in a board
deck, which is the failure the whole system is built to avoid.
"""

import json

import pytest

from apexridge.metrics import (
    BUILTIN,
    MetricDefinitionError,
    MetricRegistry,
    build_registry,
    load_custom,
    parse_spec,
)

GOOD = {
    "key": "portfolio_turnover_pct",
    "label": "Portfolio turnover",
    "unit": "pct",
    "direction": 0,
    "sane_range": [0.0, 500.0],
    "highlights_rows": ["portfolio turnover"],
}


def test_a_valid_definition_parses():
    spec = parse_spec(GOOD)
    assert spec.key == "portfolio_turnover_pct"
    assert spec.custom is True
    assert spec.highlights_rows == ("portfolio turnover",)


def test_missing_required_fields_are_rejected():
    with pytest.raises(MetricDefinitionError):
        parse_spec({"label": "No key"})
    with pytest.raises(MetricDefinitionError):
        parse_spec({"key": "no_label"})


def test_an_unknown_unit_is_rejected():
    """A unit the renderer cannot format would print a bare number with no
    indication of scale."""
    with pytest.raises(MetricDefinitionError):
        parse_spec({**GOOD, "unit": "bananas"})


def test_an_invalid_direction_is_rejected():
    """Direction drives ranking. A nonsense value would rank silently wrong."""
    with pytest.raises(MetricDefinitionError):
        parse_spec({**GOOD, "direction": 5})


def test_an_inverted_range_is_rejected():
    with pytest.raises(MetricDefinitionError):
        parse_spec({**GOOD, "sane_range": [10.0, 1.0]})


def test_a_metric_with_no_source_is_allowed_but_warned(caplog):
    """Permitted -- it renders blank everywhere with a stated reason, which is
    honest. But the author should be told rather than left guessing."""
    spec = parse_spec({"key": "unreachable", "label": "Unreachable"})
    assert spec.key == "unreachable"
    assert "declares no extraction source" in caplog.text


def test_a_custom_metric_may_not_redefine_a_builtin():
    """Silently shadowing a built-in would change a board figure's meaning
    without changing its label."""
    clash = parse_spec({"key": "management_fee_pct", "label": "Something else"})
    with pytest.raises(MetricDefinitionError):
        MetricRegistry(list(BUILTIN) + [clash])


def test_entity_type_restriction_is_respected():
    spec = parse_spec({**GOOD, "entity_types": ["interval_fund"]})
    assert spec.applies_to("interval_fund")
    assert not spec.applies_to("mortgage_reit")


def test_custom_metrics_load_from_json(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps([GOOD]))
    registry = build_registry(path)
    assert len(registry) == len(BUILTIN) + 1
    assert "portfolio_turnover_pct" in registry
    assert [s.key for s in registry.custom] == ["portfolio_turnover_pct"]


def test_a_missing_metrics_file_is_not_an_error():
    assert load_custom("/nonexistent/metrics.json") == ()


def test_a_non_list_metrics_file_is_rejected(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"key": "x"}))
    with pytest.raises(MetricDefinitionError):
        load_custom(path)


def test_shipped_example_file_is_valid():
    """The example shipped in the repo must parse, or the first thing a user
    copies is broken."""
    registry = build_registry("metrics/custom_metrics.json")
    assert len(registry.custom) == 3
    for spec in registry.custom:
        assert spec.label and spec.unit
        assert spec.prose_patterns or spec.highlights_rows or spec.xbrl_tags


def test_registry_views_update_config_in_place():
    """Modules do `from config import ALL_METRICS`, binding the object. A
    rebind would leave them iterating the built-in nine while the coverage
    report showed the custom set."""
    from apexridge import config

    original = list(config.ALL_METRICS)
    try:
        config.use_registry(build_registry("metrics/custom_metrics.json"))
        assert "portfolio_turnover_pct" in config.ALL_METRICS
        assert config.METRIC_LABELS["portfolio_turnover_pct"] == "Portfolio turnover"
        assert config.METRIC_DIRECTION["portfolio_turnover_pct"] == 0
    finally:
        config.use_registry(build_registry(None))
        assert list(config.ALL_METRICS) == original


def test_a_definition_error_names_the_file_and_the_problem():
    """A typo in a metric definition is a user error. The message has to say
    which file and which metric, or it is not actionable."""
    with pytest.raises(MetricDefinitionError) as exc:
        parse_spec({"key": "x", "label": "X", "unit": "parsecs"})
    assert "x" in str(exc.value) and "parsecs" in str(exc.value)


def test_registry_rejects_a_second_definition_of_the_same_custom_key():
    a = parse_spec({"key": "dup", "label": "One"})
    b = parse_spec({"key": "dup", "label": "Two"})
    with pytest.raises(MetricDefinitionError, match="duplicate"):
        MetricRegistry([a, b])
