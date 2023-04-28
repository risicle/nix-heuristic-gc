from dataclasses import dataclass
import enum

from humanfriendly import parse_size


class QuantityUnit(enum.Enum):
    BYTES = enum.auto()
    INODES = enum.auto()


@dataclass(slots=True)
class Quantity:
    value: int
    unit: QuantityUnit


def parse_quantity(value: str) -> Quantity:
    value = value.strip()
    if value.endswith("I"):
        if "b" in value.lower():
            raise ValueError(f"Ambiguous units for quantity {value!r}")
        value = value[:-1].strip()
        unit = QuantityUnit.INODES
    else:
        unit = QuantityUnit.BYTES

    return Quantity(parse_size(value), unit)
