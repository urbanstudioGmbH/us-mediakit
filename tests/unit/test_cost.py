import pytest

from us_mediakit.billing.cost import CostTable


def test_load_default_cost_table():
    table = CostTable.load()
    assert table.version == 1
    assert table.weights["thumbnail"] == 3


def test_credits_for_operation():
    table = CostTable.load()
    assert table.credits_for_operation("c2pa.verify") == 1


def test_credits_for_unknown_operation_raises():
    table = CostTable.load()
    with pytest.raises(ValueError):
        table.credits_for_operation("does_not_exist")


def test_credits_for_external_cost():
    table = CostTable.load()
    # micros_per_credit=500000, margin_factor=1.3 laut config/costweights.json
    credits = table.credits_for_external_cost(1_000_000)  # 1.00 Einheit externe Kosten
    assert credits == pytest.approx((1_000_000 * 1.3) / 500_000)


def test_credits_for_external_cost_without_conversion_raises():
    table = CostTable(version=1, weights={}, micros_per_credit=None, margin_factor=None)
    with pytest.raises(ValueError):
        table.credits_for_external_cost(1000)
