"""Constants for JVC Projector Integration"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final


@dataclass
class JVCConfig:
    """JVC device configuration."""

    identifier: str
    """Unique identifier of the device. (MAC Address)"""
    name: str
    """Friendly name of the device."""
    address: str
    """IP Address of device"""
    password: str = ""
    """Optional password for projector."""


@dataclass
class SensorConfig:
    """Configuration for a sensor entity."""

    identifier: str
    """Unique identifier for the sensor (e.g., 'picture_mode'). Also used as key in state_dict."""
    name: str
    """Human-readable name for the sensor."""
    query_command: str | None = None
    """Query command to retrieve sensor value (e.g., 'PMPM' for picture mode)."""
    unit: str | None = None
    """Unit of measurement (optional)."""
    default: str = ""
    """Default value when sensor is unavailable."""
    value: str | None = None
    """Current runtime value of the sensor."""
    entity: Any = None
    """Reference to the registered sensor entity instance."""


# Query command codes for sensors
QUERY_INPUT: Final = "IP"
QUERY_PICTURE_MODE: Final = "PMPM"
QUERY_LOW_LATENCY: Final = "PMLL"
QUERY_MASK: Final = "ISMA"
QUERY_LAMP_POWER: Final = "PMLP"
QUERY_LENS_APERTURE: Final = "PMDI"
QUERY_LENS_MEMORY: Final = "INML"  # Note: Read-only, no query available in protocol

SENSORS: Final[tuple[SensorConfig, ...]] = (
    SensorConfig(identifier="input", name="Input Source", query_command=QUERY_INPUT),
    SensorConfig(identifier="source", name="Signal Status", query_command=None),
    SensorConfig(
        identifier="picture_mode", name="Picture Mode", query_command=QUERY_PICTURE_MODE
    ),
    SensorConfig(
        identifier="low_latency", name="Low Latency", query_command=QUERY_LOW_LATENCY
    ),
    SensorConfig(identifier="mask", name="Screen Mask", query_command=QUERY_MASK),
    SensorConfig(
        identifier="lamp_power", name="Lamp Power", query_command=QUERY_LAMP_POWER
    ),
    SensorConfig(
        identifier="lens_aperture",
        name="Lens Aperture",
        query_command=QUERY_LENS_APERTURE,
    ),
    SensorConfig(
        identifier="lens_memory", name="Lens Memory", query_command=QUERY_LENS_MEMORY
    ),
)

LENS_MEMORY_1: Final = "INML0"
LENS_MEMORY_2: Final = "INML1"
LENS_MEMORY_3: Final = "INML2"
LENS_MEMORY_4: Final = "INML3"
LENS_MEMORY_5: Final = "INML4"
LENS_MEMORY_6: Final = "INML5"
LENS_MEMORY_7: Final = "INML6"
LENS_MEMORY_8: Final = "INML7"
LENS_MEMORY_9: Final = "INML8"
LENS_MEMORY_10: Final = "INML9"
PICTURE_MODE_FILM: Final = "PMPM00"
PICTURE_MODE_CINEMA: Final = "PMPM01"
PICTURE_MODE_NATURAL: Final = "PMPM03"
PICTURE_MODE_HDR10: Final = "PMPM04"
PICTURE_MODE_THX: Final = "PMPM06"
PICTURE_MODE_USER1: Final = "PMPM0C"
PICTURE_MODE_USER2: Final = "PMPM0D"
PICTURE_MODE_USER3: Final = "PMPM0E"
PICTURE_MODE_USER4: Final = "PMPM0F"
PICTURE_MODE_USER5: Final = "PMPM10"
PICTURE_MODE_USER6: Final = "PMPM11"
PICTURE_MODE_HLG: Final = "PMPM14"
PICTURE_MODE_FRAME_ADAPT_HDR: Final = "PMPM0B"
PICTURE_MODE_HDR10P: Final = "PMPM15"
PICTURE_MODE_PANA_PQ: Final = "PMPM16"
LOW_LATENCY_ON: Final = "PMLL1"
LOW_LATENCY_OFF: Final = "PMLL0"
MASK_OFF: Final = "ISMA2"
MASK_CUSTOM1: Final = "ISMA0"
MASK_CUSTOM2: Final = "ISMA1"
MASK_CUSTOM3: Final = "ISMA3"
LAMP_LOW: Final = "PMLP0"
LAMP_MID: Final = "PMLP2"
LAMP_HIGH: Final = "PMLP1"
LENS_APERTURE_OFF: Final = "PMDI0"
LENS_APERTURE_AUTO1: Final = "PMDI1"
LENS_APERTURE_AUTO2: Final = "PMDI2"
LENS_ANIMORPHIC_OFF: Final = "INVS0"
LENS_ANIMORPHIC_A: Final = "INVS1"
LENS_ANIMORPHIC_B: Final = "INVS2"
LENS_ANIMORPHIC_C: Final = "INVS3"
LENS_ANIMORPHIC_D: Final = "INVS4"


class SimpleCommands(StrEnum):
    """Additional simple commands of the JVC Projector not covered by media-player features."""

    LENS_MEMORY_1 = "Lens Memory 1"
    LENS_MEMORY_2 = "Lens Memory 2"
    LENS_MEMORY_3 = "Lens Memory 3"
    LENS_MEMORY_4 = "Lens Memory 4"
    LENS_MEMORY_5 = "Lens Memory 5"
    LENS_MEMORY_6 = "Lens Memory 6"
    LENS_MEMORY_7 = "Lens Memory 7"
    LENS_MEMORY_8 = "Lens Memory 8"
    LENS_MEMORY_9 = "Lens Memory 9"
    LENS_MEMORY_10 = "Lens Memory 10"
    PICTURE_MODE_FILM = "Picture Mode Film"
    PICTURE_MODE_CINEMA = "Picture Mode Cinema"
    PICTURE_MODE_NATURAL = "Picture Mode Natural"
    PICTURE_MODE_HDR10 = "Picture Mode HDR10"
    PICTURE_MODE_THX = "Picture Mode THX"
    PICTURE_MODE_USER1 = "Picture Mode User 1"
    PICTURE_MODE_USER2 = "Picture Mode User 2"
    PICTURE_MODE_USER3 = "Picture Mode User 3"
    PICTURE_MODE_USER4 = "Picture Mode User 4"
    PICTURE_MODE_USER5 = "Picture Mode User 5"
    PICTURE_MODE_USER6 = "Picture Mode User 6"
    PICTURE_MODE_HLG = "Picture Mode HLG"
    PICTURE_MODE_FRAME_ADAPT_HDR = "Picture Mode Frame Adapt HDR"
    PICTURE_MODE_HDR10P = "Picture Mode HDR10P"
    PICTURE_MODE_PANA_PQ = "Picture Mode PANA PQ"
    LOW_LATENCY_ON = "Low Latency On"
    LOW_LATENCY_OFF = "Low Latency Off"
    MASK_OFF = "Mask Off"
    MASK_CUSTOM1 = "Mask Custom 1"
    MASK_CUSTOM2 = "Mask Custom 2"
    MASK_CUSTOM3 = "Mask Custom 3"
    LAMP_LOW = "Lamp Low"
    LAMP_MID = "Lamp Mid"
    LAMP_HIGH = "Lamp High"
    LENS_APERTURE_OFF = "Lens Aperture Off"
    LENS_APERTURE_AUTO1 = "Lens Aperture Auto 1"
    LENS_APERTURE_AUTO2 = "Lens Aperture Auto 2"
    LENS_ANIMORPHIC_OFF = "Lens Anamorphic Off"
    LENS_ANIMORPHIC_A = "Lens Anamorphic A"
    LENS_ANIMORPHIC_B = "Lens Anamorphic B"
    LENS_ANIMORPHIC_C = "Lens Anamorphic C"
    LENS_ANIMORPHIC_D = "Lens Anamorphic D"
    REMOTE_ADVANCED_MENU = "Advanced Menu"
    REMOTE_PICTURE_MODE = "Picture Mode"
    REMOTE_COLOR_PROFILE = "Color Profile"
    REMOTE_LENS_CONTROL = "Lens Control"
    REMOTE_SETTING_MEMORY = "Setting Memory"
    REMOTE_GAMMA_SETTINGS = "Gamma Settings"
    REMOTE_CMD = "C.M.D"
    REMOTE_MODE_1 = "Mode 1"
    REMOTE_MODE_2 = "Mode 2"
    REMOTE_MODE_3 = "Mode 3"
    REMOTE_LENS_AP = "Lens AP"
    REMOTE_ANAMO = "Anamorphic"
    REMOTE_GAMMA = "Gamma"
    REMOTE_COLOR_TEMP = "Color Temp"
    REMOTE_3D_FORMAT = "3D Format"
    REMOTE_PIC_ADJ = "Picture Adjust"
    REMOTE_NATURAL = "Natural"
    REMOTE_CINEMA = "Cinema"
