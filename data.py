from decimal import Decimal
from typing import NamedTuple, Mapping


class TargetItem(NamedTuple):
    title: str
    url: str
    element: Mapping[str, str]


class PriceItem(NamedTuple):
    title: str
    price: Decimal
