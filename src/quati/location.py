from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt

import geonamescache

from quati.domain.job import clean_text, normalized_key

_STATE_CODES = {
    "ac": "01",
    "al": "02",
    "ap": "03",
    "am": "04",
    "ba": "05",
    "ce": "06",
    "df": "07",
    "es": "08",
    "ms": "11",
    "ma": "13",
    "mt": "14",
    "mg": "15",
    "pa": "16",
    "pb": "17",
    "pr": "18",
    "pi": "20",
    "rj": "21",
    "rn": "22",
    "rs": "23",
    "ro": "24",
    "rr": "25",
    "sc": "26",
    "sp": "27",
    "se": "28",
    "go": "29",
    "pe": "30",
    "to": "31",
}
BRAZILIAN_STATES = (
    ("AC", "Acre"),
    ("AL", "Alagoas"),
    ("AP", "Amapá"),
    ("AM", "Amazonas"),
    ("BA", "Bahia"),
    ("CE", "Ceará"),
    ("DF", "Distrito Federal"),
    ("ES", "Espírito Santo"),
    ("GO", "Goiás"),
    ("MA", "Maranhão"),
    ("MT", "Mato Grosso"),
    ("MS", "Mato Grosso do Sul"),
    ("MG", "Minas Gerais"),
    ("PA", "Pará"),
    ("PB", "Paraíba"),
    ("PR", "Paraná"),
    ("PE", "Pernambuco"),
    ("PI", "Piauí"),
    ("RJ", "Rio de Janeiro"),
    ("RN", "Rio Grande do Norte"),
    ("RS", "Rio Grande do Sul"),
    ("RO", "Rondônia"),
    ("RR", "Roraima"),
    ("SC", "Santa Catarina"),
    ("SP", "São Paulo"),
    ("SE", "Sergipe"),
    ("TO", "Tocantins"),
)
_STATE_NAME_BY_ABBR = dict(BRAZILIAN_STATES)
_STATE_ABBR_BY_KEY = {
    key: abbreviation
    for abbreviation, name in BRAZILIAN_STATES
    for key in (abbreviation.lower(), normalized_key(name))
}
_STATE_ABBR_BY_GEONAMES_CODE = {
    code: abbreviation.upper() for abbreviation, code in _STATE_CODES.items()
}
_MODE_ONLY_LOCATIONS = frozenset(
    {"", "remoto", "remote", "home office", "teletrabalho", "hibrido", "hybrid"}
)
_LOCATION_SPLIT_RE = re.compile(r"\s*(?:,|/|\s+-\s+)\s*")


@dataclass(frozen=True, slots=True)
class CityCoordinates:
    name: str
    state_code: str
    latitude: float
    longitude: float
    population: int


def _location_parts(value: str) -> tuple[str, str]:
    safe = clean_text(value, max_length=300)
    if not safe:
        return "", ""
    parts = [part.strip() for part in _LOCATION_SPLIT_RE.split(safe) if part.strip()]
    city = parts[0]
    if " - " in city:
        city, possible_state = city.rsplit(" - ", 1)
        parts.insert(1, possible_state)
    state = ""
    for part in parts[1:]:
        key = normalized_key(part)
        if key in _STATE_CODES:
            state = _STATE_CODES[key]
            break
        for abbreviation, code in _STATE_CODES.items():
            if key.endswith(f" {abbreviation}"):
                state = code
                break
    return normalized_key(city), state


@lru_cache(maxsize=1)
def _brazilian_city_index() -> dict[str, tuple[CityCoordinates, ...]]:
    by_name: dict[str, list[CityCoordinates]] = {}
    # A base de 500 habitantes cobre os municípios pequenos sem fazer chamadas externas.
    cache = geonamescache.GeonamesCache(min_city_population=500)
    for city in cache.get_cities().values():
        if city.get("countrycode") != "BR":
            continue
        coordinates = CityCoordinates(
            name=str(city.get("name", "")),
            state_code=str(city.get("admin1code", "")),
            latitude=float(city["latitude"]),
            longitude=float(city["longitude"]),
            population=int(city.get("population", 0)),
        )
        names = {coordinates.name, *city.get("alternatenames", [])}
        for name in names:
            key = normalized_key(str(name))
            if key:
                by_name.setdefault(key, []).append(coordinates)
    return {
        name: tuple(sorted(cities, key=lambda item: item.population, reverse=True))
        for name, cities in by_name.items()
    }


@lru_cache(maxsize=2_048)
def resolve_brazilian_city(location: str) -> CityCoordinates | None:
    city_name, state_code = _location_parts(location)
    if not city_name:
        return None
    candidates = _brazilian_city_index().get(city_name, ())
    if state_code:
        candidates = tuple(item for item in candidates if item.state_code == state_code)
    return candidates[0] if candidates else None


@lru_cache(maxsize=32)
def brazilian_cities(state_abbreviation: str) -> tuple[str, ...]:
    """Lista nomes canônicos da UF para os seletores da interface."""
    abbreviation = clean_text(state_abbreviation, max_length=2).upper()
    state_code = _STATE_CODES.get(abbreviation.lower())
    if state_code is None:
        return ()
    names = {
        city.name
        for cities in _brazilian_city_index().values()
        for city in cities
        if city.state_code == state_code
    }
    return tuple(sorted(names, key=normalized_key))


def split_brazilian_location(location: str) -> tuple[str, str]:
    """Separa uma localização conhecida em cidade e UF; valores ambíguos falham fechados."""
    value = clean_text(location, max_length=300)
    if not value:
        return "", ""
    key = normalized_key(value)
    if abbreviation := _STATE_ABBR_BY_KEY.get(key):
        return "", abbreviation
    resolved = resolve_brazilian_city(value)
    if resolved is None:
        return "", ""
    abbreviation = _STATE_ABBR_BY_GEONAMES_CODE.get(resolved.state_code, "")
    return (resolved.name, abbreviation) if abbreviation else ("", "")


def has_explicit_brazilian_state(location: str) -> bool:
    """Confirma que a pessoa informou uma UF, sem inferi-la apenas pelo nome da cidade."""
    value = clean_text(location, max_length=300)
    if not value:
        return False
    key = normalized_key(value)
    if key in _STATE_ABBR_BY_KEY:
        return True
    parts = [part.strip() for part in _LOCATION_SPLIT_RE.split(value) if part.strip()]
    return any(normalized_key(part) in _STATE_ABBR_BY_KEY for part in parts[1:])


def canonical_brazilian_location(city: str = "", state_abbreviation: str = "") -> str:
    """Valida cidade e UF na base offline e devolve o formato estável `Cidade, UF`."""
    safe_city = clean_text(city, max_length=120)
    abbreviation = clean_text(state_abbreviation, max_length=2).upper()
    if not safe_city and not abbreviation:
        return ""
    if abbreviation not in _STATE_NAME_BY_ABBR:
        raise ValueError("Selecione um estado brasileiro válido.")
    if not safe_city:
        return abbreviation
    resolved = resolve_brazilian_city(f"{safe_city}, {abbreviation}")
    if resolved is None:
        raise ValueError("A cidade não pertence ao estado selecionado.")
    return f"{resolved.name}, {abbreviation}"


def location_state_abbreviation(location: str) -> str:
    """Identifica a UF de uma cidade ou de uma sigla informada isoladamente."""
    _, abbreviation = split_brazilian_location(location)
    return abbreviation


def brazilian_state_name(state_abbreviation: str) -> str:
    """Converte uma sigla validada no nome oficial usado em URLs de busca."""
    return _STATE_NAME_BY_ABBR.get(clean_text(state_abbreviation, max_length=2).upper(), "")


@lru_cache(maxsize=1)
def _country_terms() -> dict[str, str]:
    terms: dict[str, str] = {}
    for country in geonamescache.GeonamesCache().get_countries().values():
        code = str(country.get("iso", "")).upper()
        for value in (country.get("name", ""), country.get("iso3", "")):
            key = normalized_key(str(value))
            if len(key) >= 3:
                terms[key] = code
    return terms


@lru_cache(maxsize=1)
def _global_city_countries() -> dict[str, frozenset[str]]:
    countries: dict[str, set[str]] = {}
    cache = geonamescache.GeonamesCache(min_city_population=15_000)
    for city in cache.get_cities().values():
        country = str(city.get("countrycode", "")).upper()
        names = {str(city.get("name", "")), *map(str, city.get("alternatenames", []))}
        for name in names:
            key = normalized_key(name)
            if key:
                countries.setdefault(key, set()).add(country)
    return {name: frozenset(values) for name, values in countries.items()}


def location_country(location: str) -> str:
    """Retorna BR, foreign ou unknown sem consultar serviços externos."""
    key = normalized_key(clean_text(location, max_length=500))
    if key in _MODE_ONLY_LOCATIONS:
        return "unknown"
    if any(name in key.split(" ") for name in {"brasil", "brazil"}):
        return "BR"
    if resolve_brazilian_city(location):
        return "BR"

    padded = f" {key} "
    for term, country_code in _country_terms().items():
        if f" {term} " in padded:
            return "BR" if country_code == "BR" else "foreign"

    city_name, _ = _location_parts(location)
    city_countries = _global_city_countries().get(city_name, frozenset())
    if city_countries and "BR" not in city_countries:
        return "foreign"
    return "unknown"


def distance_km(origin: CityCoordinates, destination: CityCoordinates) -> float:
    latitude_delta = radians(destination.latitude - origin.latitude)
    longitude_delta = radians(destination.longitude - origin.longitude)
    origin_latitude = radians(origin.latitude)
    destination_latitude = radians(destination.latitude)
    value = (
        sin(latitude_delta / 2) ** 2
        + cos(origin_latitude) * cos(destination_latitude) * sin(longitude_delta / 2) ** 2
    )
    return 2 * 6_371.0088 * asin(sqrt(value))
