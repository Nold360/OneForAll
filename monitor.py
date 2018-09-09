#!/usr/bin/env python
# sudo apt-get install python-serial

#
# This file originates from Vascofazza's Retropie open OSD project.
# Author: Federico Scozzafava
#
# THIS HEADER MUST REMAIN WITH THIS FILE AT ALL TIMES
#
# This firmware is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This firmware is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this repo. If not, see <http://www.gnu.org/licenses/>.
#

import RPi.GPIO as GPIO
import time
import os, signal, sys
import serial
from subprocess import Popen, PIPE, check_output, check_call
import re
import logging
import logging.handlers
import thread
import threading
import signal
import Adafruit_ADS1x15

adc = Adafruit_ADS1x15.ADS1015()

# Config variables
bin_dir = '/home/pi/Retropie-open-OSD/'
osd_path = bin_dir + 'osd/osd'
rfkill_path = bin_dir + 'rfkill/rfkill'

# Hardware variables
pi_charging = 26
pi_charged = 25
pi_shdn = 27
serport = '/dev/ttyACM0'

# Init GPIO pins
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(pi_charging, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pi_charged, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pi_shdn, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Batt variables
voltscale = 118.0  # ADJUST THIS
currscale = 640.0
resdivmul = 4.0
resdivval = 1000.0
dacres = 33.0
dacmax = 1023.0

batt_threshold = 4
batt_full = 420
batt_low = 330
batt_shdn = 320

temperature_max = 70.0
temperature_threshold = 5.0

# Wifi variables
wifi_state = 'UNKNOWN'
wif = 0
wifi_off = 0
wifi_warning = 1
wifi_error = 2
wifi_1bar = 3
wifi_2bar = 4
wifi_3bar = 5

audio_zero = 1;
audio_25 = 2;
audio_50 = 3;
audio_75 = 4;
audio_100 = 5;

# Set up OSD service
try:
    osd_proc = Popen(osd_path, shell=False, stdin=PIPE, stdout=None, stderr=None)
    osd_in = osd_proc.stdin
    time.sleep(1)
    osd_poll = osd_proc.poll()
    if (osd_poll):
        logging.error("ERROR: Failed to start OSD, got return code [" + str(osd_poll) + "]\n")
        sys.exit(1)
except Exception as e:
    logging.exception("ERROR: Failed start OSD binary");
    sys.exit(1);


# Check for charge state
def checkCharge():
    return not GPIO.input(pi_charging) and GPIO.input(pi_charged)


# Check for shutdown state
def checkShdn():
    state = GPIO.input(pi_shdn)
    if (state):
        logging.info("SHUTDOWN")
        doShutdown()


# Read voltage
def readVoltage():
    voltVal = adc.read_adc(0, gain=1);
    # volt = int(500.0/1023.0*voltVal)
    volt = int(((voltVal * voltscale * dacres + (dacmax * 5)) / ((dacres * resdivval) / resdivmul)))
    logging.info("VoltVal [" + str(voltVal) + "]")
    logging.info("Volt    [" + str(volt) + "]V")
    return volt


# Get voltage percent
def getVoltagepercent(volt):
    return clamp(int(float(volt - batt_shdn) / float(batt_full - batt_shdn) * 100), 0, 100)


def readAudioLevel():
    process = os.popen("amixer | grep 'Left:' | awk -F'[][]' '{ print $2 }'")
    res = process.readline()
    process.close()

    vol = 0;
    try:
        vol = int(res.replace("%", "").replace("'C\n", ""))
    except Exception, e:
        logging.info("Audio Err    : " + str(e))

    audio = 1
    if (vol <= 100):
        audio = audio_100;
    if (vol <= 75):
        audio = audio_75;
    if (vol <= 50):
        audio = audio_50;
    if (vol <= 25):
        audio = audio_25;
    if (vol == 0):
        audio = audio_zero;

    return audio;


# Read wifi (Credits: kite's SAIO project)
def readModeWifi(toggle=False):
    global wif
    ret = wif
    # check signal
    raw = check_output(['cat', '/proc/net/wireless'])
    strengthObj = re.search(r'.wlan0: \d*\s*(\d*)\.\s*[-]?(\d*)\.', raw, re.I)
    if strengthObj:
        strength = 0
        if (int(strengthObj.group(1)) > 0):
            strength = int(strengthObj.group(1))
        elif (int(strengthObj.group(2)) > 0):
            strength = int(strengthObj.group(2))
        logging.info("Wifi    [" + str(strength) + "]strength")
        if (strength > 55):
            ret = wifi_3bar
        elif (strength > 40):
            ret = wifi_2bar
        elif (strength > 5):
            ret = wifi_1bar
        else:
            ret = wifi_warning
    else:
        logging.info("Wifi    [---]strength")
        ret = wifi_error
    return ret


# Read CPU temp
def getCPUtemperature():
    res = os.popen('vcgencmd measure_temp').readline()
    return float(res.replace("temp=", "").replace("'C\n", ""))


# Do a shutdown
def doShutdown(channel=None):
    check_call("sudo killall emulationstation", shell=True)
    time.sleep(1)
    check_call("sudo shutdown -h now", shell=True)
    try:
        sys.stdout.close()
    except:
        pass
    try:
        sys.stderr.close()
    except:
        pass
    sys.exit(0)


# Signals the OSD binary
def updateOSD(volt=0, bat=0, temp=0, wifi=0, audio=0, brightness=0, info=False, charge=False):
    commands = "v" + str(volt) + " b" + str(bat) + " t" + str(temp) + " w" + str(wifi) + " a" + str(audio) + " l" + str(
        brightness) + " " + ("on " if info else "off ") + ("charge" if charge else "ncharge") + "\n"
    # print commands
    osd_proc.send_signal(signal.SIGUSR1)
    osd_in.write(commands)
    osd_in.flush()


# Misc functions
def clamp(n, minn, maxn):
    return max(min(maxn, n), minn)


global brightness
global volt
global info
global wifi
global audio
global charge
global bat

brightness = -1
info = False
volt = -1
audio = 1
wifi = 2
charge = 0
bat = 100

condition = threading.Condition()


# def reading():
#     global brightness
#     global volt
#     global info
#     global wifi
#     global audio
#     global audiocounter
#     global charge
#     global bat
#     time.sleep(1)
#     while (1):
#         condition.acquire()
#         volt = readVoltage()
#         bat = getVoltagepercent(volt)
#         wifi = readModeWifi()
#         audio = readAudioLevel()
#         updateOSD(volt, bat, 20, wifi, audio, 1, 1, charge)
#         condition.release()
#
#
# reading_thread = thread.start_new_thread(reading, ())


def lambdaCharge(channel):
    condition.acquire()
    condition.notify();
    condition.release();


def exit_gracefully(signum=None, frame=None):
    GPIO.cleanup
    osd_proc.terminate()
    sys.exit(0)


# interrupts
# GPIO.add_event_detect(pi_shdn, GPIO.FALLING, callback=doShutdown, bouncetime=500)
# GPIO.add_event_detect(pi_charging, GPIO.BOTH, callback=lambdaCharge, bouncetime=100)
# GPIO.add_event_detect(pi_charged, GPIO.FALLING, callback=lambdaCharge, bouncetime=100)

signal.signal(signal.SIGINT, exit_gracefully)
signal.signal(signal.SIGTERM, exit_gracefully)

# Main loop
try:
    print "STARTED!"
    while 1:
        # checkShdn()
        charge = checkCharge()
        audio = readAudioLevel()

        updateOSD(volt, bat, 20, wifi, audio, 1, 1, charge)
        condition.acquire()
        volt = readVoltage()
        bat = getVoltagepercent(volt)
        print bat
        wifi = readModeWifi()
        condition.wait(4.5)
        condition.release()
        time.sleep(0.5)
# print 'WAKE'

except KeyboardInterrupt:
    exit_gracefully()
