#!/usr/bin/env python

import RPi.GPIO as GPIO
import requests
import json
import papirus
import datetime
import time
import tzlocal
import subprocess as s
from subprocess import Popen
from subprocess import call
import re
import os

WUNDERGROUND_KEYFILE=os.path.join(os.path.expanduser('~'), 'wunderground.key')

BASE_URL = "http://api.wunderground.com/api/%(key)s/%(path)s%(query)s"
GEOLOOKUP = "geolookup/q/autoip.json"
CURRENT_CONDITIONS = "conditions/q/"
HOURLY = "hourly/q/"

CLEAR=26
WEATHER=19
TIME=20
NETWORK = 16
POWER = 21

SWITCHES = [
    CLEAR, 
    WEATHER, 
    TIME, 
    NETWORK, 
    POWER
]

def set_switch(channel):
    global switch
    global switch_count
    if switch == channel:
        switch_count = switch_count+1
        print "Increment switch-count on: %s to: %s" % (switch, switch_count)
    else:
        print "Set switch to: %s (was: %s)" % (channel, switch)
        switch = channel
        switch_count = 1


def write_lines(linesToWrite, size=16, clear=False):
    global lines

    if clear is True:
        text.Clear()
    else:
        for line in lines:
            text.RemoveText(line)

    del lines[:]

    counter = 0
    if len(linesToWrite) > 0:
        for line in linesToWrite:
            id = str(counter)
            text.AddText(line, 0, counter*size*1.05, size=size, Id=id, fontPath="/usr/share/fonts/opentype/cantarell/Cantarell-Bold.otf")
            lines.append(id)
            counter = counter+1

        text.WriteAll()

def clear_screen():
    return write_lines([], clear=True)

def show_current_conditions():
    write_lines(["Retrieving Weather Data..."], clear=True, size=14)

    #print "Grabbing location"
    resp = requests.get(BASE_URL % {'key': key, 'path': GEOLOOKUP, 'query': ''})
    location_query = json.loads(resp.text)['location']['requesturl'].replace('.html', '.json')
    #print "Current location request URL: %s" % location_query

    conditionsUrl = BASE_URL % {'key': key, 'path': CURRENT_CONDITIONS, 'query': location_query}
    #print "Conditions URL: %s" % conditionsUrl
    resp = requests.get(conditionsUrl)
    #print "Current conditions status code: %s" % resp.status_code
    #print "Current conditions JSON:\n\n%s\n\n" % resp.text
    conditions = json.loads(resp.text)['current_observation']

    observedTime = datetime.datetime.fromtimestamp(int(conditions['observation_epoch']))
    tz = tzlocal.get_localzone()
    observedTime = tz.localize(observedTime)

    return write_lines( 
        [u"Feels like %(feelslike_f)s\u00b0 F" % conditions, 
         "Wind: %(wind_mph)s from %(wind_dir)s" % conditions,
         "As of %s" % observedTime.strftime("%H:%M"),
         "At: %(full)s" % conditions['observation_location']])

def show_time():
    tz = tzlocal.get_localzone()
    dt = tz.localize(datetime.datetime.now())
    return write_lines([dt.strftime("%H:%M"), dt.strftime("%m/%d/%Y")], size=30)

def show_network():
    ps = Popen("ip addr show wlan0".split(), stdout=s.PIPE)
    output = ps.stdout.read()
    match = re.search('inet (\d+\.\d+\.\d+\.\d+)\/24', output)
    if match is not None:
        ip = match.group(1)
    match = re.search('link/ether\s+(\S+)\s+brd', output)
    if match is not None:
        mac = match.group(1)

    write_lines(["IP: %s" % ip, "MAC: %s" % mac], 16)

def show_wlan():
    ps = Popen("iwconfig wlan0".split(), stdout=s.PIPE)
    output = ps.stdout.read()
    match = re.search("ESSID:\"([^\"]+)\"", output)
    if match is not None:
        ssid = match.group(1)

    match = re.search("Signal level=(\S+)", output)
    if match is not None:
        signal=match.group(1)

    write_lines(["SSID: %s" % ssid, "Signal: %s" % signal], 16)

def scan_aps():
    ps = Popen("sudo iwlist scan".split(), stdout=s.PIPE)
    nets = []
    current_net=None
    while True:
        line = ps.stdout.readline()
        if line == '':
            break
        else:
            match = re.search("ESSID:\"([^\"]+)\"", line)
            if match is not None:
                current_net = {'ssid': match.group(1)}
                nets.append(current_net)
                continue

            match = re.search("Signal level=(\S+)", line)
            if match is not None:
                current_net['signal'] = match.group(1)
                continue

            match = re.search("\(Channel (\d+)\)", line)
            if match is not None:
                current_net['channel'] = match.group(1)
                continue

            match = re.search("Authentication Suites.*:\s*(\S+)", line)
            if match is not None:
                current_net['auth'] = match.group(1)
                continue

    write_lines(["%(ssid)s: %(channel)s, %(signal)s, %(auth)s" % net for net in nets][:4], size=12)

def poweroff():
    write_lines(["Shutting down in 3s..."])

    time.sleep(3)
    text.Clear()

    call("nohup sudo shutdown -P now 2>/dev/null", shell=True)

def show_ready():
    return write_lines(["Ready."])

text = papirus.PapirusTextPos(False)

global switch
global switch_count
switch = 0
switch_count = 0

handled_switch = 0
handled_count = 0

net=None
key=None
lines = []

GPIO.setmode(GPIO.BCM)
for sw in SWITCHES:
    GPIO.setup(sw, GPIO.IN)
    GPIO.add_event_detect(sw, GPIO.FALLING, callback = set_switch, bouncetime = 500)

if os.path.exists(WUNDERGROUND_KEYFILE):
    with open(WUNDERGROUND_KEYFILE) as f:
        key = f.read().rstrip()
else:
    write_lines(["WUNDERGROUND KEY NOT FOUND", "Weather function will not work."], size=10)
    time.sleep(5)

try:
    print "Ready"
    show_ready()
    while True:
        time.sleep(1)
        if handled_switch == switch and handled_count == switch_count:
            continue

        print "switch: %s, count: %s" % (switch, switch_count)
        if switch == POWER:
            print "Power Off"
            poweroff()
            break
        elif switch == CLEAR:
            print "Clear Screen"
            clear_screen()
        elif switch == WEATHER:
            print "Show Current Weather"
            show_current_conditions()
        elif switch == TIME:
            print "Show Current Time"
            show_time()
        elif switch == NETWORK:
            if switch_count == 1:
                print "Show WLAN"
                show_wlan()
            elif switch_count == 2:
                print "Show Network Info"
                show_network()
            elif switch_count == 3:
                print "Scan APs"
                scan_aps()
                switch_count = 1

        handled_switch = switch
        handled_count = switch_count
finally:
    print "Stopping"
    GPIO.cleanup()

