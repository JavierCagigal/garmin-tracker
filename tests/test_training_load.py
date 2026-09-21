from __future__ import annotations

import pytest

from garmin_tracker.training_load import edwards_trimp


def test_edwards_trimp_weights_higher_zones_more() -> None:
    # 10 minutos en cada zona: 1*10 + 2*10 + 3*10 + 4*10 + 5*10 = 150
    zones = (600.0, 600.0, 600.0, 600.0, 600.0)
    assert edwards_trimp(zones) == pytest.approx(150.0)


def test_edwards_trimp_all_in_zone_one() -> None:
    # 30 minutos solo en zona 1: 30 * 1 = 30
    zones = (1800.0, 0.0, 0.0, 0.0, 0.0)
    assert edwards_trimp(zones) == pytest.approx(30.0)


def test_edwards_trimp_missing_data_returns_none() -> None:
    assert edwards_trimp((None, None, None, None, None)) is None


def test_edwards_trimp_partial_none_treated_as_zero() -> None:
    zones = (600.0, None, None, None, None)  # solo 10 min en zona 1 registrados
    assert edwards_trimp(zones) == pytest.approx(10.0)


def test_edwards_trimp_requires_five_zones() -> None:
    with pytest.raises(ValueError):
        edwards_trimp((1.0, 2.0, 3.0))
