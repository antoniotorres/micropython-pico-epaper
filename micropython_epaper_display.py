#!/usr/bin/env python

"""
Electronic paper driver for 2.13 inch e-Paper display.

This module is based on the official Waveshare e-Paper display code.
Original repository: https://github.com/waveshare/e-Paper

File: micropython_epaper_display.py
Author: Antonio Torres

This code is released under the MIT License.
See the license terms in LICENSE file at https://opensource.org/licenses/MIT
"""

import machine
import time

# 2.13 inch e-Paper display resolution
DISPLAY_WIDTH  = 122
DISPLAY_HEIGHT = 250

# Default pin definitions for Raspberry Pi Pico W
# Pin documentation: https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html#picow-technical-specification
# Default configuration uses SPI0
DEFAULT_RST_PIN  = 4   # Reset pin - controls hardware reset of the display
DEFAULT_DC_PIN   = 0   # Data/Command pin - determines whether sent bytes are commands or data
DEFAULT_CS_PIN   = 1   # Chip Select pin - enables the display to receive data
DEFAULT_BUSY_PIN = 5   # Busy pin - indicates when the display is processing commands
DEFAULT_SCK_PIN  = 2   # SPI Clock pin - provides the clock signal for SPI communication - SCL
DEFAULT_MOSI_PIN = 3   # SPI MOSI (Master Out Slave In) pin - sends data from Pico to display - SDA

class EPaperDisplay:
    """
    Driver for 2.13 inch e-Paper display.
    
    This class provides methods to initialize and control a 2.13 inch e-Paper display
    using MicroPython. It supports full and partial refresh modes, as well as
    fast display updates.
    
    Attributes:
        width (int): Display width in pixels (122)
        height (int): Display height in pixels (250)
    """
    
    def __init__(self, rst_pin=None, dc_pin=None, cs_pin=None, busy_pin=None, sck_pin=None, mosi_pin=None, spi_id=0, baudrate=4000000):
        """
        Initialize the e-Paper display.
        
        Args:
            rst_pin (int, optional): Reset pin number. Defaults to DEFAULT_RST_PIN.
            dc_pin (int, optional): Data/Command pin number. Defaults to DEFAULT_DC_PIN.
            cs_pin (int, optional): Chip Select pin number. Defaults to DEFAULT_CS_PIN.
            busy_pin (int, optional): Busy pin number. Defaults to DEFAULT_BUSY_PIN.
            sck_pin (int, optional): SPI clock pin number. Defaults to DEFAULT_SCK_PIN.
            mosi_pin (int, optional): SPI MOSI pin number. Defaults to DEFAULT_MOSI_PIN.
            spi_id (int, optional): SPI bus ID. Defaults to 0.
            baudrate (int, optional): SPI baudrate. Defaults to 4000000.
        """
        # Use provided pins or defaults
        self.RST_PIN = rst_pin if rst_pin is not None else DEFAULT_RST_PIN
        self.DC_PIN = dc_pin if dc_pin is not None else DEFAULT_DC_PIN
        self.CS_PIN = cs_pin if cs_pin is not None else DEFAULT_CS_PIN
        self.BUSY_PIN = busy_pin if busy_pin is not None else DEFAULT_BUSY_PIN
        sck = sck_pin if sck_pin is not None else DEFAULT_SCK_PIN
        mosi = mosi_pin if mosi_pin is not None else DEFAULT_MOSI_PIN
        
        
        # Initialize SPI communication
        # Read more: https://docs.micropython.org/en/latest/library/machine.SPI.html
        # - SPI is a synchronous serial communication protocol used for display communication
        # - baudrate: Communication speed (4MHz default)
        # - polarity=0, phase=0: SPI mode 0 (most common for displays)
        # - sck: Clock signal that synchronizes data transmission
        # - mosi: Master Out Slave In - data sent from microcontroller to display
        self.spi = machine.SPI(spi_id,
                              baudrate=baudrate,
                              polarity=0,
                              phase=0,
                              sck=machine.Pin(sck),
                              mosi=machine.Pin(mosi))
        
        # Configure control pins:
        # Read more: https://docs.micropython.org/en/latest/library/machine.Pin.html#machine.Pin
        # - RST: Reset pin - when pulled low, resets the display controller
        # - DC: Data/Command pin - high for data, low for commands
        # - CS: Chip Select - pulled low to select the display for communication
        # - BUSY: Input pin that indicates when display is processing (high when busy)
        self.rst = machine.Pin(self.RST_PIN, machine.Pin.OUT)
        self.dc = machine.Pin(self.DC_PIN, machine.Pin.OUT)
        self.cs = machine.Pin(self.CS_PIN, machine.Pin.OUT)
        self.busy = machine.Pin(self.BUSY_PIN, machine.Pin.IN)
        
        self.width = DISPLAY_WIDTH
        self.height = DISPLAY_HEIGHT
    
    def power_off(self):
        """Power down the module.
        
        Sets all control pins to 0 to put the module in low power consumption mode.
        """
        self.rst.value(0)
        self.dc.value(0)
        self.cs.value(0)
        print("close 5V, Module enters 0 power consumption ...")

    def hw_reset(self):
        """Hardware reset of the display.
        
        Performs a hardware reset sequence by toggling the RST pin according to
        the e-Paper display controller timing requirements. This resets the display
        controller to its initial state and prepares it for initialization commands.
        
        The sequence consists of:
        1. Setting RST high (1) for 200μs
        2. Setting RST low (0) for 200μs (active reset)
        3. Setting RST high (1) again for 200μs
        4. Waiting for the busy signal to clear
        
        Note: Hardware reset is typically performed once at startup before
        sending any initialization commands to the display.

        Reference: Page 28 Section 13.2 https://github.com/WeActStudio/WeActStudio.EpaperModule/blob/master/Doc/ZJY122250-0213BBDMFGN-R.pdf
        """
        self.rst.value(1)        # Set reset pin high
        time.sleep_us(200)       # Wait 200 microseconds
        self.rst.value(0)        # Set reset pin low (active reset state)
        time.sleep_us(200)       # Hold in reset state for 200 microseconds
        self.rst.value(1)        # Release from reset state
        time.sleep_us(200)       # Wait 200 microseconds for internal initialization
        self.wait_until_idle()          # Wait until the display is no longer busy

    def sw_reset(self):
        """Software reset of the display.
        
        Sends the software reset command (0x12) to the display controller and
        waits for the busy signal to clear before returning. This resets the
        display controller to its initial state without toggling the hardware
        reset pin.

        Reference: Page 28 Section 13.2 https://github.com/WeActStudio/WeActStudio.EpaperModule/blob/master/Doc/ZJY122250-0213BBDMFGN-R.pdf
        """
        self.send_command(0x12)  # SWRESET - Software reset command
        time.sleep_ms(10)        # Wait 10ms as specified in the datasheet
        self.wait_until_idle()          # Wait until the display is no longer busy

    def set_display_size_and_driver_output(self):
        """Set display size and driver output control.
        
        Configures the display controller with the correct dimensions and output settings.
        This command (0x01) sets the number of gate lines, scanning sequence, and other
        driver output parameters.
        
        For 2.13 inch display:
        - First byte (0xf9): Sets gate number to 249 (F9h) which defines vertical size
        - Second byte (0x00): Gate scanning sequence setting (0 = normal direction)
        - Third byte (0x00): Left/right alternate pixel arrangement (0 = normal)
        
        Reference: Page 28 Section 13.2 https://github.com/WeActStudio/WeActStudio.EpaperModule/blob/master/Doc/ZJY122250-0213BBDMFGN-R.pdf
        """
        self.send_command(0x01)  # Driver output control      
        self.send_data(0xf9)     # Set gate number (249)
        self.send_data(0x00)     # Set gate scanning direction
        self.send_data(0x00)     # Set left/right alternate pixel arrangement

    def set_ram_data_entry_mode(self, mode=0x03):
        """Set RAM data entry mode.
        
        Configures how data is written to the display RAM. This affects the
        direction in which pixels are filled when sending data to the display.
        
        Args:
            mode (int, optional): Data entry mode value. Defaults to 0x03.
        
        Reference: Page 28 Section 13.2 https://github.com/WeActStudio/WeActStudio.EpaperModule/blob/master/Doc/ZJY122250-0213BBDMFGN-R.pdf
        """
        self.send_command(0x11)  # RAM data entry mode setting
        self.send_data(mode)

    def send_command(self, command):
        """Send command to the display.
        
        Args:
            command: Command byte to send to the register
        """
        self.dc.value(0)
        self.cs.value(0)
        self.spi.write(bytes([command]))
        self.cs.value(1)

    def send_data(self, data):
        """Send a single byte of data to the display.
        
        Args:
            data: Data byte to send
        """
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(bytes([data]))
        self.cs.value(1)

    def send_bytes(self, data):
        """Send multiple bytes of data to the display.
        
        Args:
            data: Bytes object or bytearray containing data to send
        """
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(bytes(data))
        self.cs.value(1)
    
    def wait_until_idle(self):
        """Wait until the busy_pin goes LOW.
        
        Polls the busy pin until the display is ready to accept new commands.
        """
        print("e-Paper: waiting for display to be ready...")
        while self.busy.value() == 1:      # 0: idle, 1: busy
            time.sleep_ms(10)  
        print("e-Paper: display ready")

    def display_update(self):
        """Turn on display with standard refresh.
        
        Sends the Display Update Control command (0x22) followed by a parameter byte
        that configures the display update sequence. This method only sets up the
        update parameters but does not trigger the actual display refresh.
        
        The parameter 0xF7 (binary 11110111) enables:
        - Enable clock signal
        - Enable analog
        - Load temperature value
        - Display with DISPLAY Mode 1
        - Disable analog
        - Disable OSC
        
        This is the standard high-quality refresh mode that provides the best
        image clarity but takes longer to refresh than fast modes.
        
        Note: After calling this method, you must call send_command(0x20) to
        actually start the display update sequence.
        """
        self.send_command(0x22)  # Display Update Control command
        self.send_data(0xF7)     # Standard refresh mode parameter (11110111)
                                 # Enables clock signal, analog, temperature loading,
                                 # Display Mode 1, then disables analog and OSC

    def turn_on_display(self):
        """Turn on display with standard refresh.
        
        Sends the necessary commands to update the display with normal quality.
        """
        self.display_update()
        self.send_command(0x20) # Activate Display Update Sequence
        self.wait_until_idle()

    def set_window(self, x_start, y_start, x_end, y_end):
        """Set the display update window.
        
        Args:
            x_start: X-axis starting position
            y_start: Y-axis starting position
            x_end: End position of X-axis
            y_end: End position of Y-axis
        
        Note:
            X positions must be multiples of 8 or the last 3 bits will be ignored.
        """
        self.send_command(0x44) # SET_RAM_X_ADDRESS_START_END_POSITION
        # x point must be the multiple of 8 or the last 3 bits will be ignored
        self.send_data((x_start>>3) & 0xFF)
        self.send_data((x_end>>3) & 0xFF)
        
        self.send_command(0x45) # SET_RAM_Y_ADDRESS_START_END_POSITION
        self.send_data(y_start & 0xFF)
        self.send_data((y_start >> 8) & 0xFF)
        self.send_data(y_end & 0xFF)
        self.send_data((y_end >> 8) & 0xFF)

    def set_cursor(self, x, y):
        """Set the cursor position for the next data write.
        
        Args:
            x: X-axis position
            y: Y-axis position
            
        Note:
            X position must be a multiple of 8 or the last 3 bits will be ignored.
        """
        self.send_command(0x4E) # SET_RAM_X_ADDRESS_COUNTER
        # x point must be the multiple of 8 or the last 3 bits will be ignored
        self.send_data(x & 0xFF)
        
        self.send_command(0x4F) # SET_RAM_Y_ADDRESS_COUNTER
        self.send_data(y & 0xFF)
        self.send_data((y >> 8) & 0xFF)

    def init(self):
        """Initialize the e-Paper display.
        
        Performs the hardware initialization sequence for the display,
        configuring it for normal operation mode. This implementation follows
        the "Normal Operation Flow" described in section 13.1 (Typical Operating Sequence)
        on page 27 of the display controller datasheet.
        
        Reference: https://github.com/WeActStudio/WeActStudio.EpaperModule/blob/master/Doc/ZJY122250-0213BBDMFGN-R.pdf
        
        Returns:
            int: 0 on success
        """
        # HW Reset
        self.hw_reset()

        # SW Reset
        self.sw_reset()

        self.set_display_size_and_driver_output()

        self.set_ram_data_entry_mode()

        self.set_window(0, 0, self.width-1, self.height-1)
        self.set_border()
        
        self.wait_until_idle()
    
    def display(self, image):
        """Send image buffer to e-Paper and display it.
        
        This method sends the provided image data to the display's RAM and
        triggers a display refresh to show the image on screen.
        
        Args:
            image: Byte array containing the image data to display.
                   Each byte represents 8 horizontal pixels (1 bit per pixel).
        """
        self.set_cursor(0, 0)        # Set cursor to top-left corner
        self.send_command(0x24)      # WRITE_RAM command - write to display RAM
        self.send_bytes(image)       # Send the entire image buffer
        self.turn_on_display()       # Refresh the display to show the new image
    
    def clear(self, color=0xFF):
        """Clear the display screen.
        
        Fills the entire display with the specified color (white by default).
        
        Args:
            color (int, optional): Color to fill the screen with.
                - 0xFF: White (default)
                - 0x00: Black
        """
        # Calculate line width in bytes (each byte represents 8 horizontal pixels)
        if self.width % 8 == 0:
            linewidth = int(self.width / 8)
        else:
            linewidth = int(self.width / 8) + 1
        
        # Create a buffer filled with the specified color
        buffer = [color] * int(self.height * linewidth)
        
        # Send the buffer to the display and refresh
        self.display(buffer)

    def deep_sleep(self):
        """Enter deep sleep mode.
        
        Sends the deep sleep command (0x10) to the display controller with the
        parameter 0x01 to put the display in ultra-low power consumption mode.
        
        In deep sleep mode, the display maintains its current image but stops
        responding to most commands until a hardware reset is performed.
        This is useful for battery-powered applications to conserve energy.
        
        Reference: Page 28 Section 13.2 https://github.com/WeActStudio/WeActStudio.EpaperModule/blob/master/Doc/ZJY122250-0213BBDMFGN-R.pdf
        """
        self.send_command(0x10)  # DEEP_SLEEP_MODE command
        self.send_data(0x01)     # Enter deep sleep mode 1 (lowest power consumption)

    def set_border(self, value=0xC0):
        """Set the border control.
        
        Configures the border behavior of the display. This affects how
        the non-image border area of the display appears during and after refresh.
        
        Args:
            value (int, optional): Border control value. Defaults to 0xC0.
                - 0xC0: Border with black/white/black pattern (default)
                - 0x80: Border with white/black/white pattern
                - 0x00: Border with black pattern
                - 0x40: Border with white pattern
        
        Reference: Page 28 Section 13.2 https://github.com/WeActStudio/WeActStudio.EpaperModule/blob/master/Doc/ZJY122250-0213BBDMFGN-R.pdf
        """
        self.send_command(0x3C)  # Set border command
        self.send_data(value)    # Set border value
