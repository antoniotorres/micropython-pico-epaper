# micropython-pico-epaper

A MicroPython example for controlling e-paper displays with Raspberry Pi Pico.

## Overview

This project provides a simple interface for controlling e-paper (e-ink) displays using MicroPython on the Raspberry Pi Pico.

## Features

- Simple API for controlling e-paper displays
- Power-efficient with deep sleep support
- Bitmap display capabilities
- Compatible with Raspberry Pi Pico and MicroPython

## Development Environment

This project is designed to work with [MicroPico](https://github.com/paulober/MicroPico), a Visual Studio Code extension that simplifies MicroPython development for Raspberry Pi Pico boards. MicroPico provides features like:

- Code auto-completion with documentation
- Terminal integration for MicroPython REPL
- Easy file transfer between your computer and Pico
- Project management tools

I recommend installing MicroPico for the best development experience.

## Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/micropython-pico-epaper.git
```

## Usage

Basic example:

```python
#!/usr/bin/env python

from micropython_epaper_display import EPaperDisplay
import time

# Initialize the display
epd = EPaperDisplay()
epd.init()
epd.clear()

# Enter deep sleep to save power
epd.deep_sleep()
epd.power_off()
```
