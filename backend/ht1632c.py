#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
HT1632 python driver
Used to control HT1632 Sure Electronics panels

Resources:
    This driver has been realized using those tutorials:
    - https://github.com/zzxydg/RaspPi-ht1632c/blob/master/HT1632C_LEDDriver.py
        This tuto was useful for GPIO configuration
    - https://github.com/pinski1/MessageBoard
        And this one useful for SPI configuration and panels connection
    Thanks to their authors for sharing their experience.

Hardware:
    Shopping list:
    - 4x HT1632C monocolor from Sure Electronics
    - 1x74HCT138 mux
    - 1x raspberry pi 
    - power supply 220-5v/3A

Connections:
    PSU   RASPI        74HCT38       HT1632C
    VCC --   2  ------   VCC
            15  ------   A0
            16  ------   A1
            18  ------   A2
            19  --------------------  7
    GND --------------   E1
    GND --------------   E2
            22  ------   E3
            23  --------------------  5   
    GND --  25  --------------------  8
                         Y0   ------  3
                         Y1   ------  1
                         Y2   ------  2
                         Y3   ------  4

    All panels are connected together (data + power supply)
    First panel's jumpers are set to 1, second panel's jumpers to 2...
"""

import RPi.GPIO as GPIO
import time
import spidev
import logging
import numpy as np
from scipy.ndimage.interpolation import shift
from threading import Thread, Lock
from datetime import datetime
import re

class InvalidPanel(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)

class InvalidBuffer(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)

class ScrollingMessage(Thread):
    """
    Scrolling message thread
    Use to scroll specified message until end of thread
    """

    def __init__(self, board_size, message_length, buf, buf_index, direction, speed, write_pixels_callback, reset_callback):
        """
        Constructor

        Args:
            board_size (int): board size
            message_length (int): message length
            buf () : buffer
            buf_index (int): buffer index
            direction (int): scroll direction
            speed (float): message speed (pause between each step)
            write_pixels_callback (function): write pixel callback
            reset_callback (function): reset screen callback
        """
        #init
        Thread.__init__(self)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)

        #members
        self.board_size = board_size
        self.message_length = message_length
        self.buf = buf
        self.buf_index = buf_index
        self.direction = direction
        self.speed = speed
        self.write_pixels = write_pixels_callback
        self.reset = reset_callback
        self.__continu = True

    def stop(self):
        """
        Stop scrolling message
        """
        self.__continu = False

    def run(self):
        """
        Scrolling message process
        """
        while self.__continu:
            try:
                #make buffer copy
                copy = np.copy(self.buf)

                #compute max scrolling position
                max_scrolling = self.board_size + self.message_length

                #scroll message to board
                while max_scrolling>=0 and self.__continu:
                    #display message
                    self.write_pixels(copy, self.buf_index)

                    #shift buffer content
                    if self.direction==0:
                        copy = shift(copy, 1, cval=0)
                    else:
                        copy = shift(copy, -1, cval=0)

                    #decrease number of scroll to process
                    max_scrolling -= 1

                    #pause
                    time.sleep(float(self.speed))

                #force buffer deletion
                del copy
                copy = None

                #auto reset hardware if needed
                self.reset()

            except:
                self.logger.exception(u'Exception in scrolling message:')
            
#https://unicode-table.com/en/
FONT5x7 = [
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [0x00,0x00,0x00,0x00,0x00], #
    [0x00,0x00,0xfa,0x00,0x00], # !
    [0x00,0xe0,0x00,0xe0,0x00], # "
    [0x28,0xfe,0x28,0xfe,0x28], # #
    [0x24,0x54,0xfe,0x54,0x48], # $
    [0xc4,0xc8,0x10,0x26,0x46], # %
    [0x6c,0x92,0xaa,0x44,0x0a], # &
    [0x00,0xa0,0xc0,0x00,0x00], # '
    [0x00,0x38,0x44,0x82,0x00], # (
    [0x00,0x82,0x44,0x38,0x00], # )
    [0x10,0x54,0x38,0x54,0x10], # *
    [0x10,0x10,0x7c,0x10,0x10], # +
    [0x00,0x0a,0x0c,0x00,0x00], # ,
    [0x10,0x10,0x10,0x10,0x10], # -
    [0x00,0x06,0x06,0x00,0x00], # .
    [0x04,0x08,0x10,0x20,0x40], # /
    [0x7c,0x8a,0x92,0xa2,0x7c], # 0
    [0x00,0x42,0xfe,0x02,0x00], # 1
    [0x42,0x86,0x8a,0x92,0x62], # 2
    [0x84,0x82,0xa2,0xd2,0x8c], # 3
    [0x18,0x28,0x48,0xfe,0x08], # 4
    [0xe4,0xa2,0xa2,0xa2,0x9c], # 5
    [0x3c,0x52,0x92,0x92,0x0c], # 6
    [0x80,0x8e,0x90,0xa0,0xc0], # 7
    [0x6c,0x92,0x92,0x92,0x6c], # 8
    [0x60,0x92,0x92,0x94,0x78], # 9
    [0x00,0x6c,0x6c,0x00,0x00], # :
    [0x00,0x6a,0x6c,0x00,0x00], # ;
    [0x00,0x10,0x28,0x44,0x82], # <
    [0x28,0x28,0x28,0x28,0x28], # =
    [0x82,0x44,0x28,0x10,0x00], # >
    [0x40,0x80,0x8a,0x90,0x60], # ?
    [0x4c,0x92,0x9e,0x82,0x7c], # @
    [0x7e,0x88,0x88,0x88,0x7e], # A
    [0xfe,0x92,0x92,0x92,0x6c], # B
    [0x7c,0x82,0x82,0x82,0x44], # C
    [0xfe,0x82,0x82,0x44,0x38], # D
    [0xfe,0x92,0x92,0x92,0x82], # E
    [0xfe,0x90,0x90,0x80,0x80], # F
    [0x7c,0x82,0x82,0x8a,0x4c], # G
    [0xfe,0x10,0x10,0x10,0xfe], # H
    [0x00,0x82,0xfe,0x82,0x00], # I
    [0x04,0x02,0x82,0xfc,0x80], # J
    [0xfe,0x10,0x28,0x44,0x82], # K
    [0xfe,0x02,0x02,0x02,0x02], # L
    [0xfe,0x40,0x20,0x40,0xfe], # M
    [0xfe,0x20,0x10,0x08,0xfe], # N
    [0x7c,0x82,0x82,0x82,0x7c], # O
    [0xfe,0x90,0x90,0x90,0x60], # P
    [0x7c,0x82,0x8a,0x84,0x7a], # Q
    [0xfe,0x90,0x98,0x94,0x62], # R
    [0x62,0x92,0x92,0x92,0x8c], # S
    [0x80,0x80,0xfe,0x80,0x80], # T
    [0xfc,0x02,0x02,0x02,0xfc], # U
    [0xf8,0x04,0x02,0x04,0xf8], # V
    [0xfe,0x04,0x18,0x04,0xfe], # W
    [0xc6,0x28,0x10,0x28,0xc6], # X
    [0xc0,0x20,0x1e,0x20,0xc0], # Y
    [0x86,0x8a,0x92,0xa2,0xc2], # Z
    [0x00,0x00,0xfe,0x82,0x82], # [
    [0x40,0x20,0x10,0x08,0x04], # "\"
    [0x82,0x82,0xfe,0x00,0x00], # ]
    [0x60,0x90,0x90,0x60,0x00], # °
    [0x02,0x02,0x02,0x02,0x02], # _
    [0x00,0x80,0x40,0x20,0x00], # `
    [0x04,0x2a,0x2a,0x2a,0x1e], # a
    [0xfe,0x12,0x22,0x22,0x1c], # b
    [0x1c,0x22,0x22,0x22,0x04], # c
    [0x1c,0x22,0x22,0x12,0xfe], # d
    [0x1c,0x2a,0x2a,0x2a,0x18], # e
    [0x10,0x7e,0x90,0x80,0x40], # f
    [0x10,0x28,0x2a,0x2a,0x3c], # g
    [0xfe,0x10,0x20,0x20,0x1e], # h
    [0x00,0x22,0xbe,0x02,0x00], # i
    [0x04,0x02,0x22,0xbc,0x00], # j
    [0x00,0xfe,0x08,0x14,0x22], # k
    [0x00,0x82,0xfe,0x02,0x00], # l
    [0x3e,0x20,0x18,0x20,0x1e], # m
    [0x3e,0x10,0x20,0x20,0x1e], # n
    [0x1c,0x22,0x22,0x22,0x1c], # o
    [0x3e,0x28,0x28,0x28,0x10], # p
    [0x10,0x28,0x28,0x18,0x3e], # q
    [0x3e,0x10,0x20,0x20,0x10], # r
    [0x12,0x2a,0x2a,0x2a,0x04], # s
    [0x20,0xfc,0x22,0x02,0x04], # t
    [0x3c,0x02,0x02,0x04,0x3e], # u
    [0x38,0x04,0x02,0x04,0x38], # v
    [0x3c,0x02,0x0c,0x02,0x3c], # w
    [0x22,0x14,0x08,0x14,0x22], # x
    [0x30,0x0a,0x0a,0x0a,0x3c], # y
    [0x22,0x26,0x2a,0x32,0x22], # z
    [0x00,0x10,0x6c,0x82,0x00], # {
    [0x00,0x00,0xfe,0x00,0x00], # |
    [0x00,0x82,0x6c,0x10,0x00], # }
    [0x00,0x00,0x00,0x00,0x00], # ~
    [0x00,0x00,0x00,0x00,0x00], #
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    [0x00,0x40,0xA0,0x40,0x00] #°
]

FONT_INVALID = [0x28,0xfe,0x28,0xfe,0x28] # '#'

LOGOS = {
    #smileys
    ':)' : [0x3C,0x42,0xA9,0x85,0xA5,0x89,0x42,0x3C],
    ':(' : [0x3C,0x42,0xA5,0x89,0xA9,0x85,0x42,0x3C],
    ':D' : [0x3C,0x42,0xAD,0x85,0xA5,0x8D,0x42,0x3C],
    ':]' : [0x3C,0x42,0xAD,0x85,0xA5,0x8D,0x42,0x3C],
    ':|' : [0x3C,0x42,0xA5,0x85,0xA5,0x85,0x42,0x3C],
    ':[' : [0x3C,0x42,0xAD,0x89,0xA9,0x8D,0x42,0x3C],
    ':o' : [0x3C,0x42,0xA1,0x8D,0xAD,0x81,0x42,0x3C],
    ':O' : [0x3C,0x42,0xAD,0x8D,0xAD,0x8D,0x42,0x3C],
    #misc
    ':shit' : [0x06,0x0D,0x15,0xD5,0xB5,0x95,0x41,0x32,0x0C],
    ':skull': [0x78,0xDF,0xDE,0xF7,0xDE,0xDF,0x78],
    ':alien': [0x78,0xCC,0xE6,0xFF,0xE6,0xCC,0x78],
    ':heart': [0x70,0x88,0x84,0x82,0x41,0x82,0x84,0x88,0x70],
    ':cat': [0x1c,0x62,0x89,0x59,0x23,0x2b,0x59,0x81,0x62,0x1c],
    ':bat': [0x78,0x84,0x88,0x90,0x88,0x44,0x48,0x2c,0xfe,0x41,0x2b,0x23,0x2b,0x41,0xfe,0x2c,0x48,0x44,0x88,0x90,0x88,0x84,0x78],
    ':clock': [0x10,0x22,0x41,0x79,0x49,0x2A,0x1C],
    #direction
    ':left': [0x18,0x3C,0x7E,0xFF,0x3C,0x3C,0x3C],
    ':right': [0x3C,0x3C,0x3C,0xFF,0x7E,0x3C,0x18],
    ':up': [0x10,0x30,0x7F,0xFF,0xFF,0x7F,0x30,0x10],
    ':down': [0x08,0x0C,0xFE,0xFF,0xFF,0xFE,0x0C,0x08],
    #weather
    ':sunny': [0x08,0x89,0x5a,0x24,0xc2,0x43,0x24,0x5a,0x91,0x10],
    ':rainy': [0x39,0x46,0x85,0x86,0x85,0x66,0x25,0x26,0x18],
    ':cloudy': [0x38,0x44,0x84,0x84,0x84,0x64,0x24,0x24,0x18],
    ':stormy': [0x18,0x2b,0x5e,0x94,0x98,0x8b,0x5e,0x54,0x38],
    ':foggy': [0x34,0x4c,0x95,0x95,0x95,0x75,0x31,0x11,0x11],
    ':snowy': [0x32,0x4d,0x8a,0x8d,0x8a,0x6d,0x2a,0x2d,0x10],
    ':night': [0x3c,0x42,0x99,0xa5,0xc3,0x42]
}
PATTERN_REPLACEMENT = '^'

class HT1632C():
    """
    HT1632C driver class
    """

    HT1632_ID_CMD      = 0b100   # ID = 100 - Commands
    HT1632_ID_RD       = 0b110   # ID = 110 - Read RAM
    HT1632_ID_WR       = 0b101   # ID = 101 - Write RAM
    HT1632_CMD_SYSDIS  = 0x00    # CMD = 0000-0000-x Turn off osc
    HT1632_CMD_SYSON   = 0x01    # CMD = 0000-0001-x Enable system osc
    HT1632_CMD_LEDOFF  = 0x02    # CMD = 0000-0010-x LEDs off
    HT1632_CMD_LEDON   = 0x03    # CMD = 0000-0011-x LEDs on
    HT1632_CMD_BLOFF   = 0x08    # CMD = 0000-1000-x Blink off
    HT1632_CMD_BLON    = 0x09    # CMD = 0000-1001-x Blink on
    HT1632_CMD_SLVMD   = 0x10    # CMD = 0001-0000-x Slave Mode
    HT1632_CMD_MSTMD   = 0x14    # CMD = 0001-0100-x Master Mode
    HT1632_CMD_RCCLK   = 0x18    # CMD = 0001-1000-x Use on-chip clock
    HT1632_CMD_EXTCLK  = 0x1C    # CMD = 0001-1100-x Use external clock
    HT1632_CMD_COMS00  = 0x20    # CMD = 0010-0000-x NMOS 8 x 32
    HT1632_CMD_COMS01  = 0x24    # CMD = 0010-0100-x NMOS 16 x 24
    HT1632_CMD_COMS10  = 0x28    # CMD = 0010-1000-x PMOS 8 x 32
    HT1632_CMD_COMS11  = 0x2C    # CMD = 0010-1100-x PMOS 16 x 24
    HT1632_CMD_PWM     = 0xA0    # CMD = 1010-PPPP-x PWM duty cycle

    ALL_LEDS_OFF =  [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

    ALL_LEDS_ON =  [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

    TEST =  [0xFF, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

    SCROLL_LEFT_TO_RIGHT = 0
    SCROLL_RIGHT_TO_LEFT = 1

    RESET_HW_DELAY = 60

    def __init__(self, pin_a0, pin_a1, pin_a2, pin_e3, panel_count):
        """
        Constructor

        Args:
            pin_ao (int): pin connected to A0
            pin_a1 (int): pin connected to A1
            pin_e3 (int): pin connected to E3
            panel_count (int): number of HT1632C panels
        """
        #init
        self.logger = logging.getLogger(self.__class__.__name__)
        #self.logger.setLevel(logging.DEBUG)

        #members
        self.__lock = Lock()
        self.__pin_a0 = pin_a0
        self.__pin_a1 = pin_a1
        self.__pin_a2 = pin_a2
        self.__pin_e3 = pin_e3
        self.__panel_count = panel_count
        self.__scrolling_thread = None
        self.speed = 0.05
        self.direction = HT1632C.SCROLL_RIGHT_TO_LEFT
        self.unit_days = u'days'
        self.unit_hours = u'hours'
        self.unit_minutes = u'mins'
        self.__turned_on = True
        self.__last_hw_reset = None
        self.__panel_cleared = {}

        #configure gpios
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.__pin_a0, GPIO.OUT)
        GPIO.setup(self.__pin_a1, GPIO.OUT)
        GPIO.setup(self.__pin_a2, GPIO.OUT)
        #e3 is always on
        GPIO.setup(self.__pin_e3, GPIO.OUT, initial=GPIO.HIGH)

        #init hardware
        self.__init_hardware()

    def __init_hardware(self):
        """
        Init hardware (GPIO, SPI, HT1632C)
        """
        #configure spi
        self.__spi = spidev.SpiDev(0, 0)
        self.__spi.max_speed_hz = 976000
        self.__spi.mode = 3

        #configure panels
        for panel in range(self.__panel_count):
            #flag panel is not cleared
            self.__panel_cleared[panel] = False
            #enable master mode
            self.__write_command_to_panel(panel, HT1632C.HT1632_CMD_RCCLK)
            #enable system oscillator
            self.__write_command_to_panel(panel, HT1632C.HT1632_CMD_SYSON)
            #enable LEDs
            self.__write_command_to_panel(panel, HT1632C.HT1632_CMD_LEDON)
            #set brightness (16/16)
            self.__write_command_to_panel(panel, HT1632C.HT1632_CMD_PWM | 0x0F)
            #disable blink
            self.__write_command_to_panel(panel, HT1632C.HT1632_CMD_BLOFF)

        #update last hardware reset
        self.__last_hw_reset = time.time()

    def __reset_hardware(self):
        """
        Reset hardware
        """
        if time.time()>(self.__last_hw_reset+HT1632C.RESET_HW_DELAY):
            self.logger.info(u'Reset hardware')
            #clean everything
            #self.cleanup()
            #close spi
            if self.__spi:
                self.__spi.close()

            #init hardware again
            self.__init_hardware()

    def set_scroll_speed(self, speed):
        """
        Set default scroll speed

        Args:
            speed (float): speed (in seconds)
        """
        self.speed = speed

    def set_direction(self, direction):
        """
        Set default direction

        Args:
            direction (0|1): direction (0: left->right, 1: right->left)
        """
        self.direction = direction

    def set_time_units(self, days, hours, minutes):
        """
        Set default time units. Used to display time units in your language

        Args:
            days (string): days string
            hours (string): hours string
            minutes (string): minutes string
        """
        self.unit_days = days
        self.unit_hours = hours
        self.unit_minutes = minutes

    def cleanup(self):
        """
        Clean everything
        """
        #stop scrolling thread
        self.__stop_scrolling_thread()

        #clear screen
        self.logger.debug(u'Clear board')
        self.clear()
        time.sleep(0.25)

        #cleanup gpio
        self.logger.debug(u'Cleanup GPIOs')
        GPIO.cleanup()
        time.sleep(0.25)

        #close spi
        if self.__spi:
            self.__spi.close()

    def __stop_scrolling_thread(self):
        """
        Stop scrolling thread if necessary
        """
        if self.__scrolling_thread!=None:
            self.logger.debug(u'Stop scrolling thread')
            self.__scrolling_thread.stop()
            #self.__scrolling_thread.join(1.0)
            time.sleep(0.25)
            self.__scrolling_thread = None
            
    def __select_panel(self, panel):
        """
        Select specified panel number
        A small pause is executed to make sure GPIO are updated before sending data to SPI
        
        Args:
            panel (int): panel number
        """
        if panel==0:
            GPIO.output(self.__pin_a0, GPIO.LOW)
            GPIO.output(self.__pin_a1, GPIO.LOW)
            GPIO.output(self.__pin_a2, GPIO.LOW)
            #time.sleep(0.001)
        elif panel==1:
            GPIO.output(self.__pin_a0, GPIO.HIGH)
            GPIO.output(self.__pin_a1, GPIO.LOW)
            GPIO.output(self.__pin_a2, GPIO.LOW)
            #time.sleep(0.001)
        elif panel==2:
            GPIO.output(self.__pin_a0, GPIO.LOW)
            GPIO.output(self.__pin_a1, GPIO.HIGH)
            GPIO.output(self.__pin_a2, GPIO.LOW)
            #time.sleep(0.001)
        elif panel==3:
            GPIO.output(self.__pin_a0, GPIO.HIGH)
            GPIO.output(self.__pin_a1, GPIO.HIGH)
            GPIO.output(self.__pin_a2, GPIO.LOW)
            #time.sleep(0.001)
        else:
            GPIO.output(self.__pin_a0, GPIO.HIGH)
            GPIO.output(self.__pin_a1, GPIO.HIGH)
            GPIO.output(self.__pin_a2, GPIO.HIGH)
            #panel unselect doesn't need to pause system
            #because we don't need to sync gpio and spi

    def __write_command_to_panel(self, panel, command):
        """
        Write command to specified panel
        
        Args:
            panel (int): panel number
            command (hex): command to send
        """
        #prepare command
        buf = [(HT1632C.HT1632_ID_CMD << 5) | (command >> 3), (command << 5)]
        
        #select panel to send command to
        self.__lock.acquire(True)
        self.__select_panel(panel)

        #write command and read result
        res = self.__spi.writebytes(buf)
        
        #unselect panel
        self.__select_panel(None)
        self.__lock.release()
        
        return res

    def __write_pixels_to_panel(self, panel, pixels):
        """
        Write pixels buffer to specified panel
        
        Args:
            panel: panel number
            pixels: pixels buffer
        """
        #prepare buffer
        buf =  [(HT1632C.HT1632_ID_WR << 5) & 0xE0, ((0x3F & pixels[0]) >> 2),
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        for i in range(32):
            buf[i+2] = ((pixels[i] << 6) & 0xC0) | ((pixels[(i+1) % 32] >> 2) & 0x3F)

        #check buffer
        non_zeros = np.count_nonzero(buf[2:])
        if non_zeros==0:
            #buffer is empty
            if not self.__panel_cleared[panel]:
                #panel not empty yet, let's process this time
                self.__panel_cleared[panel] = True
            else:
                #panel already cleared, stop now
                return 0
        else:
            self.__panel_cleared[panel] = False

        #select panel to send command to
        self.__lock.acquire(True)
        self.__select_panel(panel)

        #write buffer and read result
        res = self.__spi.writebytes(buf)

        #unselect panel
        self.__select_panel(None)
        self.__lock.release()
        
        return res

    def __write_pixels(self, pixels, index=0):
        """
        Write pixels to board
        Buffer must be large enough for current board

        Args:
            pixels: buffer of pixels
            index: if buffer is too large, index can be used to get index of buffer to display.
                If buffer is still too large, buffer is adjusted to board size.

        Raises:
            BufferInvalid
        """
        #check size
        if len(pixels)<self.__get_board_size():
            #buffer is not large enough
            raise InvalidBuffer(u'Buffer is not large enough (awaited size:%d, found size:%d)' % (self.__get_board_size(), len(pixels)))
        if len(pixels)-index<self.__get_board_size():
            raise InvalidBuffer(u'Buffer is too short if index applied. Please provide larger buffer')

        #get only board size part of buffer
        if index>0 or len(pixels)>self.__get_board_size():
            pixels = pixels.tolist()[index: index+self.__get_board_size()]
        else:
            pixels = pixels.tolist()
        
        #display buffer on each panels
        for panel in range(self.__panel_count):
            #get pixels for current panel
            panel_pixels = pixels[panel*32:panel*32+32]
            #send pixels to current panel
            self.__write_pixels_to_panel(panel, panel_pixels)

    def __append_letter(self, buf, letter, position):
        """
        Append letter to specified buffer

        Args:
            buf: pixels buffer. can be None to compute buffer buffer length
            letter: letter to write
            position: current position in buffer

        Returns:
            int: new position in buffer
        """
        if letter!=PATTERN_REPLACEMENT:
            try:
                unicode_letter = letter.decode('utf-8')
                font_letter = FONT5x7[ord(unicode_letter)]
            except:
                #invalid char
                font_letter = FONT_INVALID
            font_size = len(font_letter)
            for col in range(font_size):
                if buf is not None:
                    buf[position] = font_letter[col]
                position += 1
        return position

    def __append_logo(self, buf, logo, position):
        """
        Append logo to specified buffer

        Args:
            buf: pixels buffer. Can be None to compute buffer length
            logo: logo to write
            position: current position in buffer

        Returns:
            int: new position in buffer
        """
        font_size = len(LOGOS[logo])
        for col in range(font_size):
            if buf is not None:
                buf[position] = LOGOS[logo][col]
            position += 1
        return position

    def __append_text(self, buf, text, position):
        """
        Append text to specified buffer
        
        Args:
            buf: pixels buffer. Can be None to compute buffer length
            text: text to write
            position: current position in buffer

        Returns:
            new position in buffer
        """
        self.logger.debug(u'append text %s @ %d' % (text, position))
        text_size = len(text)
        for col in range(text_size):
            position = self.__append_letter(buf, text[col], position)
        return position

    def __get_board_size(self):
        """
        Return default buffer size

        Returns:
            int: board size
        """
        return self.__panel_count*32

    def __get_buffer(self, size=None):
        """
        Return empty buffer that fits current board size
        
        Args:
            size: you can get custom buffer of specified size

        Returns:
            numpy.ndarray: empty buffer (filled of zeros)
        """
        board_size = self.__get_board_size()
        if size is None:
            #no size specified, return board size buffer
            return np.zeros((board_size,), dtype=np.uint8)

        elif size<board_size:
            #requested buffer size is not larger enought, return board size
            self.logger.debug(u'Requested size is not larger enough, return board size buffer')
            return np.zeros((board_size,), dtype=np.uint8)

        else:
            #size is larger than board size, allocate buffer as requested
            return np.zeros((size,), dtype=np.uint8)

    def __human_readable_duration(self, timestamp):
        """
        Return human readable duration

        Returns:
            string: duration
        """
        if timestamp<3600:
            return u'%d %s' % (int(float(timestamp)/60.0), self.unit_minutes)
        elif timestamp<86400:
            return u'%d %s' % (int(float(timestamp)/3600.0), self.unit_hours)
        else:
            return u'%d %s' % (int(float(timestamp)/86400.0), self.unit_days)

    def __search_for_patterns(self, message):
        """
        Search for patterns in message (logos, time...)
        
        Args:
            message: input message

        Returns:
            tuple: found_logos: dict of found logos (logo index:found logo string),
                message: modified message (logo strings are replaced by constant PATTERN_REPLACEMENT),
                evolutive: True if message contains evolutive fields (like time),
        """
        found_patterns = {}
        evolutive = False

        #search for logos
        for logo in LOGOS:
            pos = 0
            while pos!=-1:
                pos = message.find(logo)
                if pos!=-1:
                    #found logo
                    message = message.replace(logo, PATTERN_REPLACEMENT*len(logo), 1)
                    found_patterns[pos] = {u'type':u'logo', u'value':logo}
        
        #search for time pattern
        now_ts = time.time()
        now_dt = datetime.fromtimestamp(now_ts)
        for match in list(re.finditer(u'(:time)(:[0-9]+)?', message)):
            message = message.replace(match.group(0), PATTERN_REPLACEMENT*len(match.group(0)), 1)
            evolutive = True
            if match.group(2) is not None:
                #timestamp specified, compute duration
                ts = int(match.group(2)[1:])
                if now_ts<=ts:
                    found_patterns[match.start()] = {u'type':u'text', u'value':u'%s' % self.__human_readable_duration(ts-now_ts)}
                else:
                    #timestamp is behind now
                    found_patterns[match.start()] = {u'type':u'text', u'value':u'[OVER]'}
            else:
                #only time tag specified, add current time
                found_patterns[match.start()] = {u'type':u'text', u'value':u'%0.2d:%0.2d' % (now_dt.hour, now_dt.minute)}

        return found_patterns, message, evolutive

    def __get_message_length(self, message, patterns):
        """
        Compute message length

        Args:
            message: message with logos replaced (see __search_for_patterns function)
            logos: logos indexes

        Returns:
            int: buffer position
        """
        buffer_position = 0

        for index in range(len(message)):
            if index in patterns.keys():
                if patterns[index][u'type']==u'logo':
                    buffer_position = self.__append_logo(None, patterns[index][u'value'], buffer_position)
                elif patterns[index][u'type']==u'text':
                    buffer_position = self.__append_text(None, patterns[index][u'value'], buffer_position)
            else:
                buffer_position = self.__append_letter(None, message[index], buffer_position)

        return buffer_position

    def clear(self):
        """
        Clear board (all pixels turned off)
        """
        #stop scrolling thread if necessary
        self.__stop_scrolling_thread()

        #and display empty message
        for panel in range(self.__panel_count):
            #turn all leds on
            self.__write_pixels_to_panel(panel, HT1632C.ALL_LEDS_OFF)

    def display_message(self, message, position=0):
        """
        Display message to board

        Args:
            message: message to display
            position: position of message in board (if message is too long it will be truncated)

        Returns:
            bool: True if message is evolutive or False if board is off or message not evolutive
        """
        buffer_position = 0

        #auto reset hardware if needed
        self.__reset_hardware()

        #drop message if board is off
        if not self.__turned_on:
            self.logger.debug(u'Board is turned off')
            return False

        #search for patterns in message
        patterns, message, evolutive = self.__search_for_patterns(message)

        #get message length
        message_length = self.__get_message_length(message, patterns)
        self.logger.debug(u'message length=%d' % message_length)

        #stop existing scrolling thread
        self.__stop_scrolling_thread()

        #scroll or display message
        if message_length>self.__get_board_size():
            #scroll message
            self.logger.debug(u'Add scrolling message')

            #get buffer
            buf = self.__get_buffer(self.__get_board_size() + message_length)

            #fill buffer
            buffer_position = 0
            if self.direction==0:
                buffer_index = message_length
                buffer_position = 0
            else:
                buffer_index = 0
                buffer_position = len(buf) - message_length
            for index in range(len(message)):
                if index in patterns.keys():
                    if patterns[index][u'type']==u'logo':
                        buffer_position = self.__append_logo(buf, patterns[index][u'value'], buffer_position)
                    elif patterns[index][u'type']==u'text':
                        buffer_position = self.__append_text(buf, patterns[index][u'value'], buffer_position)
                else:
                    buffer_position = self.__append_letter(buf, message[index], buffer_position)

            #launch scrolling thread
            self.__scrolling_thread = ScrollingMessage(self.__get_board_size(), message_length, buf, buffer_index, self.direction, self.speed, self.__write_pixels, self.__reset_hardware)
            self.__scrolling_thread.start()

        else:
            #display message
            self.logger.debug(u'Add NOT scrolling  message')

            #get buffer
            buf = self.__get_buffer(message_length)

            #fill buffer
            #buf = self.__get_buffer(message_length)
            for index in range(len(message)):
                if index in patterns.keys():
                    if patterns[index][u'type']==u'logo':
                        buffer_position = self.__append_logo(buf, patterns[index][u'value'], buffer_position)
                    elif patterns[index][u'type']==u'text':
                        buffer_position = self.__append_text(buf, patterns[index][u'value'], buffer_position)
                else:
                    buffer_position = self.__append_letter(buf, message[index], buffer_position)

            #shift buffer if necessary
            buf = shift(buf, position, cval=0)
            
            #write buffer to panels
            self.__write_pixels(buf)

        return evolutive

    def scroll_message_once(self, message, speed=0.05, direction=0):
        """
        Scroll message to board

        Args:
            message: message to display
            speed: animation speed
            direction: scroll direction

        Returns:
            bool: True if message is evolutive or False if board is off or message not evolutive
        """
        font_size = 5

        #drop message if board is off
        if not self.__turned_on:
            return False

        #search for logos in message
        patterns, message, evolutive = self.__search_for_patterns(message)

        #get message length
        message_length = self.__get_message_length(message, patterns)
        self.logger.debug(u'message length=%d' % message_length)

        #fill buffer
        buf = self.__get_buffer(self.__get_board_size() + message_length)
        buffer_position = 0
        if direction==0:
            buffer_index = message_length
            buffer_position = 0
        else:
            buffer_index = 0
            buffer_position = len(buf) - message_length
        for index in range(len(message)):
            if index in patterns.keys():
                if patterns[index][u'type']==u'logo':
                    buffer_position = self.__append_logo(buf, patterns[index][u'value'], buffer_position)
                elif patterns[index][u'type']==u'text':
                    buffer_position = self.__append_text(buf, patterns[index][u'value'], buffer_position)
            else:
                buffer_position = self.__append_letter(buf, message[index], buffer_position)
        
        #scroll message
        max_scrolling = self.__get_board_size() + message_length
        while max_scrolling>=0:
            #display message
            self.__write_pixels(buf, buffer_index)
            #shift buffer content
            if direction==0:
                buf = shift(buf, 1, cval=0)
            else:
                buf = shift(buf, -1, cval=0)
            #decrease number of scroll to process
            max_scrolling -= 1
            #pause
            time.sleep(speed)

        return evolutive
 
    def random(self, duration, speed=0.025):
        """
        Turn on/off pixels randomly

        Args:
            duration: animation duration (in s)
        """
        for i in range(int(float(duration)/float(speed))):
            buf = np.random.randint(0, 255, self.__get_board_size())
            self.__write_pixels(buf)
            time.sleep(float(speed))

    def display_animation(self):
       """
       Display programmed animation
        
       Args:
            animation: name of animation
       """
       pass

    def set_time_units(self, minutes, hours, days):
        """
        Set time units. Useful to change string according to your lang

        Args:
            minutes: minutes
            hours: hours
            days: days
        """
        self.unit_days = days
        self.unit_hours = hours
        self.unit_minutes = minutes

    def turn_on(self):
        """
        Turn on board
        """
        self.logger.debug(u'Turn on display')
        #enable display
        self.__turned_on = True

    def turn_off(self):
        """
        Turn off board
        """
        self.logger.debug(u'Turn off display')
        #disable display
        self.__turned_on = False

        #and clear board
        self.clear()

    def is_on(self):
        """
        Return display state

        Returns:
            bool: True if display is on
        """
        return self.__turned_on

    def test(self):
        self.clear()
        #all pixels on
        #for panel in range(self.__panel_count):
        #    #turn all leds on
        #    self.__write_pixels(panel, HT1632C.TEST)
        #time.sleep(4.0)

        #all pixels off
        #for panel in range(self.__panel_count):
        #    #turn all leds on
        #    self.__write_pixels(panel, HT1632C.ALL_LEDS_OFF)

        #display message
        #self.display_message('hello world!')
        #self.display_message('hello world!', 15)
        #self.display_message(':):(:D:):|:[:]:o:O')
        #self.display_message('sunny cloudy rainy stormy snowy foggy night')
        #self.display_message('left right up down')
        #self.display_message('shit skull alien bat cat heart')
        self.display_message('il est time et midi est dans time:1480417200')

        #display long message (auto scroll)
        #self.display_message('verrrrryyyyyyyyyyy long message!')
        #time.sleep(10.0)

        #scroll message once
        #self.scroll_message_once('Hello World', direction=self.SCROLL_RIGHT_TO_LEFT)
        #self.scroll_message_once('Hello World', direction=self.SCROLL_LEFT_TO_RIGHT)
        #self.scroll_message_once('Fucking shit of bat')
  
        #random
        #self.random(5)

        time.sleep(5.0)
        

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(name)s %(levelname)s : %(message)s")
    pin_a0 = 15
    pin_a1 = 16
    pin_a2 = 18
    pin_e3 = 22
    panels = 4
    leds = HT1632C(pin_a0, pin_a1, pin_a2, pin_e3, panels)
    leds.test()
    leds.cleanup()
    #GPIO.cleanup()
