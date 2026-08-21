import pytest

from quati.location import (
    brazilian_cities,
    canonical_brazilian_location,
    split_brazilian_location,
)


def test_offline_city_catalog_covers_small_brazilian_municipalities() -> None:
    cities = brazilian_cities("SP")

    assert "Itu" in cities
    assert "Sorocaba" in cities
    assert len(cities) > 500


def test_location_is_canonicalized_with_city_and_state() -> None:
    assert canonical_brazilian_location("sorocaba", "sp") == "Sorocaba, SP"
    assert split_brazilian_location("Sorocaba / SP") == ("Sorocaba", "SP")


def test_location_rejects_city_from_another_state() -> None:
    with pytest.raises(ValueError, match="não pertence"):
        canonical_brazilian_location("Sorocaba", "RJ")


def test_state_only_location_is_supported() -> None:
    assert canonical_brazilian_location("", "SP") == "SP"
    assert split_brazilian_location("SP") == ("", "SP")
