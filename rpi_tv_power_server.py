#!/usr/bin/env python
import urllib2
from subprocess import PIPE, Popen, call, check_output, CalledProcessError
import xmltodict
import time
from threading import Thread
import os
import sys
import socket
import pyxhook as hooklib

TIMEOUT = 10 * 60 #seconds

#############################
# Regular Keypress Monitoring

global keyPressTimeout
keyPressTimeout = time.time()

def OnKeyDownEvent(ignored):
    print "press"
    global keyPressTimeout
    global sleepActive
    keyPressTimeout = time.time()
    sleepActive = False

def OnKeyUpEvent(ignored):
    global keyPressTimeout
    global sleepActive
    keyPressTimeout = time.time()
    sleepActive = False

def getXset():
    return Popen(['xset', '-q'], env={"PATH":"/usr/bin/", "DISPLAY":":0"}, stderr=PIPE, stdout=PIPE).stdout.read()


hm = hooklib.HookManager()
hm.KeyDown = OnKeyDownEvent
hm.KeyUp = OnKeyUpEvent
hm.start()

#############################
# Lirc Keypress Monitoring

def lirc_irw_output(out):
    for unused in iter(out.readline, b''):
        print "press"
        global keyPressTimeout
        global sleepActive
        keyPressTimeout = time.time()
        sleepActive = False

ON_POSIX = 'posix' in sys.builtin_module_names
p = Popen(['irw'], stdout=PIPE, stdin=PIPE, bufsize=1, close_fds=ON_POSIX)
t = Thread(target=lirc_irw_output, args=(p.stdout,))
t.daemon = True # thread dies with the program
t.start()

#############################
# Network reporting

def network_server(s):
    global sleepActive
    while True:
        c, addr = s.accept()     # Establish connection with client.

        while True:
            data = c.recv(1024)
            if not data:
                break
            c.send('off' if sleepActive else 'on')
        c.close()                # Close the connection

s = socket.socket()         # Create a socket object
host = socket.gethostname() # Get local machine name
port = 55555                # Reserve a port for your service.
s.bind((host, port))        # Bind to the port

s.listen(5)                 # Now wait for client connection.

nt = Thread(target=network_server, args=(s,))
nt.daemon = True # thread dies with the program
nt.start()


#############################
# Runtime Loop

global sleepActive
sleepActive = False

timeout = 0
playstate = 'idle'
prevplaystate = playstate
while True:

    # Mythfrontend status
    mythStatus = urllib2.urlopen("http://localhost:6547/Frontend/GetStatus").read()
    status = xmltodict.parse(mythStatus)

    state = None
    playspeed = None
    for entry in status[u'FrontendStatus'][u'State']['String']: 
        if entry['Key'] == 'state':
            state = entry['Value']
            #print entry['Value']
        if entry['Key'] == 'playspeed':
            playspeed = entry['Value']

    if 'idle' in state:
        playstate = 'idle'

    if 'Watching' in state:
        if '1' in playspeed:
            playstate = 'playing'
        else:
            playstate = 'pause'


    if prevplaystate != playstate:
        print playstate

    prevplaystate = playstate


    if playstate == 'playing':
        keyPressTimeout = time.time()

    if time.time() - keyPressTimeout > TIMEOUT:
        # Go To Sleep
        if not sleepActive:
            print "Sleep"
        sleepActive = True

    else:
        if sleepActive:
            print "Wake"
        sleepActive = False

    time.sleep(0.5)
