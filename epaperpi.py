#!/usr/bin/env python

import RPi.GPIO as GPIO
import requests
import json
import papirus
import datetime
import time
from time import sleep
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

CLR_SW=26
CURR_SW=19
TIME_SW=20
NET_SW = 16
PWR_SW = 21

text = papirus.PapirusTextPos(False)

GPIO.setmode(GPIO.BCM)
GPIO.setup(CLR_SW, GPIO.IN)
GPIO.setup(CURR_SW, GPIO.IN)
GPIO.setup(TIME_SW, GPIO.IN)
GPIO.setup(NET_SW, GPIO.IN)
GPIO.setup(PWR_SW, GPIO.IN)

net=None
key=None
lines = []
if os.path.exists(WUNDERGROUND_KEYFILE):
    with open(WUNDERGROUND_KEYFILE) as f:
        key = f.read().rstrip()
else:
    lines = write_lines(lines, ["WUNDERGROUND KEY NOT FOUND", "Weather function will not work."], size=10)
    sleep(5)

def write_lines(lines, linesToWrite, size=16, clear=False):
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
    return lines

def clear_screen(lines):
    return write_lines(lines, [], clear=True)

def show_current_conditions(lines):
    lines = write_lines(lines, ["Retrieving Weather Data..."], clear=True, size=14)

    #print "Grabbing location"
    resp = requests.get(BASE_URL % {'key': key, 'path': GEOLOOKUP, 'query': ''})
    location_query = json.loads(resp.text)['location']['requesturl'].replace('.html', '.json')
    #print "Current location request URL: %s" % location_query

    conditionsUrl = BASE_URL % {'path': CURRENT_CONDITIONS, 'query': location_query}
    #print "Conditions URL: %s" % conditionsUrl
    resp = requests.get(conditionsUrl)
    #print "Current conditions status code: %s" % resp.status_code
    #print "Current conditions JSON:\n\n%s\n\n" % resp.text
    conditions = json.loads(resp.text)['current_observation']

    observedTime = datetime.datetime.fromtimestamp(int(conditions['observation_epoch']))
    tz = tzlocal.get_localzone()
    observedTime = tz.localize(observedTime)

    return write_lines(lines, 
        [u"Feels like %(feelslike_f)s\u00b0 F" % conditions, 
         "Wind: %(wind_mph)s from %(wind_dir)s" % conditions,
         "As of %s" % observedTime.strftime("%H:%M"),
         "At: %(full)s" % conditions['observation_location']])

def show_time(lines):
    tz = tzlocal.get_localzone()
    dt = tz.localize(datetime.datetime.now())
    return write_lines(lines, [dt.strftime("%H:%M"), dt.strftime("%m/%d/%Y")], size=30)

def show_network(lines):
    ps = Popen("ip addr show wlan0".split(), stdout=s.PIPE)
    output = ps.stdout.read()
    match = re.search('inet (\d+\.\d+\.\d+\.\d+)\/24', output)
    if match is not None:
        ip = match.group(1)
    match = re.search('link/ether\s+(\S+)\s+brd', output)
    if match is not None:
        mac = match.group(1)

    ps = Popen("iwconfig wlan0".split(), stdout=s.PIPE)
    output = ps.stdout.read()
    match = re.search("ESSID:\"([^\"]+)\"", output)
    if match is not None:
        ssid = match.group(1)

    match = re.search("Signal level=(\S+)", output)
    if match is not None:
        signal=match.group(1)

    if ip is None or mac is None or ssid is None:
        return
    else:
        net = {'ip': ip, 'mac': mac, 'ssid': ssid, 'signal': signal}

    return write_lines(lines, ["IP: %(ip)s" % net, "MAC: %(mac)s" % net, "SSID: %(ssid)s" % net, "Signal: %(signal)s" % net], 16)

def poweroff(lines):
    write_lines(lines, ["Shutting down in 3s..."])

    sleep(3)
    text.Clear()

    call("nohup sudo shutdown -P now 2>/dev/null", shell=True)

def show_ready(lines):
    return write_lines(lines, ["Ready."])

lines = []
try:
    print "Ready"
    lines = show_ready(lines)
    while True:
        if GPIO.input(PWR_SW) == GPIO.LOW:
            print "Power Off"
            poweroff(lines)
            break
        elif GPIO.input(CLR_SW) == GPIO.LOW:
            print "Clear Screen"
            lines = clear_screen(lines)
        elif GPIO.input(CURR_SW) == GPIO.LOW:
            print "Show Current Weather"
            lines = show_current_conditions(lines)
        elif GPIO.input(TIME_SW) == GPIO.LOW:
            print "Show Current Time"
            lines = show_time(lines)
        elif GPIO.input(NET_SW) == GPIO.LOW:
            print "Show Network Info"
            lines = show_network(lines)

        sleep(0.1)
finally:
    print "Stopping"
    GPIO.cleanup()

