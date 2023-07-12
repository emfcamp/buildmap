from typing import Optional
from decimal import Decimal
from functools import total_ordering
from enum import Enum
import pint

unit = pint.UnitRegistry()

COUPLER_LOSS = Decimal("0.2")
FIBRE_LOSS = Decimal("0.5")
CONNECTOR_LOSS = Decimal("0.1")


class LinkType():
    Copper = "copper"
    Fibre = "fibre"


@total_ordering
class Location:
    """The `cores_required` attribute indicates how many uplink
    cores this switch requires - usually 1 bidi link in our case."""

    def __init__(self, name: str, cores_required: int = 1, deployed: bool = False):
        self.name = name
        self.cores_required = cores_required
        self.deployed = deployed

    def __repr__(self) -> str:
        return "<Switch {}>".format(self.name)

    def __eq__(self, other):
        if type(other) != type(self):
            return False
        return self.name.lower() == other.name.lower()

    def __gt__(self, other):
        if type(other) != type(self):
            return False
        return self.name.lower() > other.name.lower()

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)


class Link:
    def __init__(
        self,
        from_location: Location,
        to_location: Location,
        type: LinkType,
        length: int,
        cores: int,
        aggregated: bool,
        deployed: bool,
        fibre_name: Optional[str],
    ):
        self.from_location = from_location
        self.to_location = to_location
        self.type = type
        self.length = length
        self.cores = cores
        self.cores_used = 0
        self.aggregated = aggregated
        self.fibre_name = fibre_name
        self.deployed = deployed

    def __repr__(self) -> str:
        return "<Link {from_switch} -> {to_switch} ({type})>".format(
            from_switch=self.from_location,
            to_switch=self.to_location,
            type=self.type.value,
        )


class LogicalLink:
    """A logical link represents a direct network path between two switches.
    Logical links can span more than one physical cable when the link is passively
    patched/coupled through an intermediate location.
    """

    def __init__(self, from_location: Location, to_location: Location, type):
        self.from_location = from_location
        self.to_location = to_location
        self.type = type
        self.physical_links: list[Link] = []

    @property
    def total_length(self) -> float:
        return sum(link.length for link in self.physical_links)

    @property
    def couplers(self) -> int:
        return len(self.physical_links) - 1

    @property
    def deployed(self):
        return all(link.deployed for link in self.physical_links)

    def loss(self):
        """Return an approximation of loss in dB"""

        if self.type == LinkType.Copper:
            raise ValueError("Can't calculate link loss for copper!")

        # Pint struggles with the dimensions here for some reason, so calculate with magnitudes and convert to dB.
        return (
            (self.couplers * COUPLER_LOSS)
            + (self.total_length.magnitude * FIBRE_LOSS)
            + (2 * CONNECTOR_LOSS)
        ) * unit.dB

    def __repr__(self):
        return "<LogicalLink {from_switch} -> {to_switch} ({type})>".format(
            from_switch=self.from_location,
            to_switch=self.to_location,
            type=self.type.value,
        )
