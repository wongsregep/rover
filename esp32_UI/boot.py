import esp
esp.osdebug(None)

import gc
gc.collect()

import network
import os, esp32

from machine import reset, Pin, Signal 

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect('<wifi ssid>', '<password>')

pwrled_pin = Pin(33, Pin.OUT)
pwrled = Signal(pwrled_pin, invert=True)
pwrled.on()

import webrepl
webrepl.start()

