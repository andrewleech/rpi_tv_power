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
import logging
import logging.handlers
#import pydevd

#pydevd.settrace('192.168.0.9', port=2345, stdoutToServer=True, stderrToServer=True)

from twisted.internet import reactor
from twisted.cred import portal, checkers
from twisted.conch import manhole, manhole_ssh


def debugThread(my_globals):

    def getManholeFactory(namespace):
        realm = manhole_ssh.TerminalRealm()
        def getManhole(_):
            return manhole.Manhole(namespace)
        realm.chainedProtocolFactory.protocolFactory = getManhole
        p = portal.Portal(realm)
        p.registerChecker(
            checkers.InMemoryUsernamePasswordDatabaseDontUse(admin='diskdisk'))
        f = manhole_ssh.ConchFactory(p)
        return f

    reactor.listenTCP(2222, getManholeFactory(my_globals))

    reactor.run()

#dt = Thread(target=debugThread, args=(globals(),))
#dt.daemon = True # thread dies with the program
#dt.start()



TIMEOUT = 10 * 60 #seconds
os.environ['DISPLAY'] = ":0"
LOG_PATH='/tmp/tv_suspend.log'


###########
# Logging

FORMAT="%(asctime)-15s : %(message)s"
logHandler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=2*1024*1024, backupCount=2)
logHandler.setFormatter(logging.Formatter(FORMAT))
logger = logging.getLogger('log')
logger.setLevel(logging.DEBUG)
logger.addHandler(logHandler)


#############################
# Regular Keypress Monitoring

global keyPressTimeout
keyPressTimeout = time.time() - TIMEOUT + 90    # Start with 1.5 minute to sleep

def OnKeyDownEvent(ignored):
    print "press"
    logger.debug("idle: keypress")
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
    ret = None
    try:
        ret = Popen(['xset', '-q'], env={"PATH":"/usr/bin/", "DISPLAY":":0"}, stderr=PIPE, stdout=PIPE).stdout.read()
    except Exception as e:
        logger.warn("exception in getXset(): " + str(e))
    return ret


hm = hooklib.HookManager()
hm.KeyDown = OnKeyDownEvent
hm.KeyUp = OnKeyUpEvent
hm.start()

#############################
# Lirc Keypress Monitoring

def lirc_irw_output(out):
    for unused in iter(out.readline, b''):
        print "press"
        logger.debug("idle: lirc press")
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
    global timeout
    global lastNetwork

    while True:
        try:
            c, addr = s.accept()     # Establish connection with client.

            while True:
                data = c.recv(1024)
                if not data:
                    break
                if data == "t":
                    c.send(str(timeout))
                    lastNetwork = time.time()
                else:
                    c.send('off' if sleepActive else 'on')
                    lastNetwork = time.time()
            c.close()                # Close the connection
        except Exception as e:
            logger.warn("exception in network_server(): " + str(e))


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

global timeout
global lastNetwork
timeout = 0
lastNetwork = time.time()
playstate = 'idle'
prevplaystate = playstate

lastStat = time.time()

while True:
    try:

        if (time.time() - lastStat) > 60:
            logger.debug("idleTime: " + str((time.time() - keyPressTimeout)/60))
            lastStat = time.time()

        # Mythfrontend status
        status = None
        try:
            mythStatusHttp = urllib2.urlopen("http://localhost:6547/Frontend/GetStatus", timeout=2)
            if mythStatusHttp:
                mythStatus = mythStatusHttp.read()
                status = xmltodict.parse(mythStatus)
        except urllib2.URLError:
            pass

        state = None
        playspeed = None
        if status:
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
                logger.debug("mythfrontend: " + playstate)

            prevplaystate = playstate


            if playstate == 'playing':
                keyPressTimeout = time.time()

        if time.time() - keyPressTimeout > TIMEOUT:
            # Go To Sleep
            if not sleepActive:
                print "Sleep"
                logger.debug("timeout: sleep")
            sleepActive = True

            # Comms has dropped out, let system service manager restart
            if time.time() - lastNetwork > TIMEOUT:
                exit()

        else:
            if sleepActive:
                print "Wake"
                logger.debug("timeout: wake")
            sleepActive = False

        time.sleep(0.5)
    except Exception as e:
        logger.warn("exception in main(): " + str(e))

