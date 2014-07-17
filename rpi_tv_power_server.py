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
import Xlib.error
import logging
import logging.handlers
#import pydevd
import Queue

import mythtv_status
import xbmc_status

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


###########
# Logging

FORMAT="%(asctime)-15s : %(message)s"
#logHandler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=2*1024*1024, backupCount=2)
logHandler = logging.StreamHandler(sys.stdout)
logHandler.setFormatter(logging.Formatter(FORMAT))
logger = logging.getLogger('log')
logger.setLevel(logging.DEBUG)
logger.addHandler(logHandler)

logger.debug("Startup")

resetQueue = Queue.Queue()

#############################
# Regular Keypress Monitoring

keyPressTimeout = time.time() - TIMEOUT + 90    # Start with 1.5 minute to sleep

def OnKeyDownEvent(ignored):
    #print "press"
    logger.debug("keypress")
    resetQueue.put("keypress")

def OnKeyUpEvent(ignored):
    pass
    #global keyPressTimeout
    #global sleepActive
    #keyPressTimeout = time.time()
    #sleepActive = False


def createHookManager(disp):
    hm = hooklib.HookManager(disp)
    hm.KeyDown = OnKeyDownEvent
    hm.KeyUp = OnKeyUpEvent
    hm.start()
    return hm


def xHooksThread(logger):

    hms = {
            ":0" : None,
            ":1" : None
          }

    while True:
        for disp in hms:
            try:
                try:
                    if hms[disp]._Thread__stopped:
                        raise AttributeError
                except AttributeError:
                    time.sleep(5)
                    logger.debug("Starting xhook on display %s" % str(disp))
                    hms[disp] = createHookManager(disp)
            except Exception as e:
                logger.debug("Error in xhook on display %s" % str(disp))
                logger.exception(e)
                time.sleep(30)
        time.sleep(10)


ON_POSIX = 'posix' in sys.builtin_module_names

xt = Thread(target=xHooksThread, args=(logger,))
xt.daemon = True # thread dies with the program
xt.start()


#############################
# Lirc Keypress Monitoring

def lirc_irw_output(out):
    for unused in iter(out.readline, b''):
        #print "press"
        logger.debug("lirc press")
        resetQueue.put("lirc")
        #global keyPressTimeout
        #global sleepActive
        #keyPressTimeout = time.time()
        #sleepActive = False

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
last_mythtv_status = False
last_xbmc_status = False

mythtvStatus = mythtv_status.mythtv_status()

while True:
    try:

        if not resetQueue.empty():
            resetQueue.get(timeout=10)
            keyPressTimeout = time.time()

        if (time.time() - lastStat) > 60:
            logger.debug("idleTime: " + str((time.time() - keyPressTimeout)/60))
            lastStat = time.time()

        # Monitor MythTV
        current_mythtv_status = mythtvStatus.getStatus()
        if current_mythtv_status:
            if not last_mythtv_status:
                logger.debug("mythtv start playing")
            keyPressTimeout = time.time()
        elif last_mythtv_status:
            logger.debug("mythtv stop playing")
        last_mythtv_status = current_mythtv_status

        # Monitor XBMC
        try:
            current_xbmc_status = xbmc_status.getStatus()
            if current_xbmc_status:
                if not last_xbmc_status:
                    logger.debug("xbmc start playing")
                keyPressTimeout = time.time()
            elif last_xbmc_status:
                logger.debug("xbmc stop playing")
            last_xbmc_status = current_xbmc_status
        except xbmc_status.Timeout:
            pass

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
        logger.warn("exception in main()")
        logger.exception(e)

