"""Constants for JVC Projector Integration"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from jvcprojector import command


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
    capabilities: list[str] | None = None
    """Cached list of supported projector capabilities (command names)."""
    use_sensors: bool = True
    """Enable or disable sensor entities."""


@dataclass
class SensorConfig:
    """Configuration for a sensor entity."""

    identifier: str
    """Unique identifier for the sensor (e.g., 'picture_mode'). Also used as key in state_dict."""
    name: str
    """Human-readable name for the sensor."""
    query_command: Any = None
    """Query command class to retrieve sensor value (e.g., command.PictureMode)."""
    unit: str | None = None
    """Unit of measurement (optional)."""
    default: str = ""
    """Default value when sensor is unavailable."""
    value: str | None = None
    """Current runtime value of the sensor."""
    entity: Any = None
    """Reference to the registered sensor entity instance."""


# Map of command class names to sensor configurations
# Filtered at runtime based on what the connected projector actually supports
SENSORS: Final[dict[str, SensorConfig]] = {
    "Input": SensorConfig(
        identifier="input",
        name="Input Source",
        query_command=command.Input,
    ),
    "Source": SensorConfig(
        identifier="source",
        name="Signal Source",
        query_command=command.Source,
    ),
    "PictureMode": SensorConfig(
        identifier="picture_mode",
        name="Picture Mode",
        query_command=command.PictureMode,
    ),
    "LowLatencyMode": SensorConfig(
        identifier="low_latency",
        name="Low Latency",
        query_command=command.LowLatencyMode,
    ),
    "Mask": SensorConfig(
        identifier="mask",
        name="Screen Mask",
        query_command=command.Mask,
    ),
    "LightPower": SensorConfig(
        identifier="lamp_power",
        name="Lamp Power",
        query_command=command.LightPower,
    ),
    "IntelligentLensAperture": SensorConfig(
        identifier="lens_aperture",
        name="Lens Aperture",
        query_command=command.IntelligentLensAperture,
    ),
    "Anamorphic": SensorConfig(
        identifier="anamorphic",
        name="Anamorphic Mode",
        query_command=command.Anamorphic,
    ),
    "ColorProfile": SensorConfig(
        identifier="color_profile",
        name="Color Profile",
        query_command=command.ColorProfile,
    ),
    "LensMemory": SensorConfig(
        identifier="lens_memory",
        name="Lens Memory",
        query_command=None,
    ),
}


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
