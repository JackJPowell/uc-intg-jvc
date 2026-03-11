# JVC integration for Remote Two Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## v1.3.1 - 2026-03-11

### Fixed

- Corrected a bug where select entity would trigger connection timeouts

### Changed

- Updated JVC projector library to extend support for additional projector models

---

## v1.3.0 - 2026-03-09

#### Select Entities

Select entities allow you to view and change projector settings directly from the remote UI. Available selects are dynamically enabled based on your projector's capabilities.

### Added

- **Picture Mode** — Select from all supported picture modes (Film, Cinema, Natural, HDR10, THX, User 1-6, HLG, HDR10+, Frame Adapt HDR, PANA PQ, etc.)
- **Lens Aperture** — Control the intelligent lens aperture (Off, Auto 1, Auto 2)
- **Color Profile** — Select the active color profile
- **Anamorphic** — Set the anamorphic mode (Off, A, B, C, D)
- **Low Latency Mode** — Toggle low latency mode on or off
- **Mask** — Set the screen mask (Off, Custom 1, Custom 2, Custom 3)
- **Lamp Power** — Set lamp/laser power level (Low, Mid, High)
- **Installation Mode** — Select the lens memory / installation mode (Memory 1–10)
- **Content Type** — Set the content type (Auto, SDR, HDR10, HDR10+, HLG)

---

## v0.1.0 - 2024-03-31

### Added

- First version.
