#!/usr/bin/env python

import sys
from subprocess import PIPE, Popen
from threading  import Thread
import time
import socket

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x

import logging
import logging.handlers


CEC_DEBUG = True

MYTH_IP = "192.168.0.9"
MYTH_SOCKET = 55555
LOG_PATH='/home/corona/tv_suspend.log'
NET_TIMEOUT = 11 * 60 #seconds

#logging
FORMAT="%(asctime)-15s : %(message)s"
logHandler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=2*1024*1024, backupCount=2)
logHandler.setFormatter(logging.Formatter(FORMAT))
logger = logging.getLogger('log')
logger.setLevel(logging.DEBUG)
logger.addHandler(logHandler)


# Holds current internal bool of desired TV power
desiredOn = True

# Holds current internal bool of measured TV power
currentlyOn = False

# Holds current internal representation of active tv input source
activeSource = "myth"

global expectActiveSource
expectActiveSource = None

def cecGetPowerStatus():
    p.stdin.write("pow 0.0.0.0\n") # get current power status

def cecGetActiveSource():
    global expectActiveSource
    expectActiveSource = time.time()
    p.stdin.write("tx 1f:85\n") # get current power status

def cec_thread(out, queue):
    global expectActiveSource

    for line in iter(out.readline, b''):
        if CEC_DEBUG:
            logger.debug("cec: " + line.replace('\n',''))

        # TV power status
        if "TV (0): power status changed from " in line or 'power status:' in line:
            queue.put({"id":"tv power", "val":(True if "to 'on'" in line or ': on' in line else False)})

        # TV input channel
        if expectActiveSource:
            if time.time() - expectActiveSource < 2:
                if "making TV (0) the active source" in line or "TV (0) was already marked as active source" in line:
                    queue.put({"id":"active source", "val":"TV"})
            if time.time() - expectActiveSource > 2:
                queue.put({"id":"active source", "val":"myth"})
                expectActiveSource = None

        if "making TV (0) the active source" in line:
            queue.put({"id":"active source", "val":"TV"})

        if "making Recorder 1 (1) the active source" in line:
            queue.put({"id":"active source", "val":"rpi"})

        if "0f:80:40:00:10:00" in line or \
           "0f:a0:08:00:46:00:13:00:10:80:00:01:00:00:00:00" in line:
            queue.put({"id":"active source", "val":"myth"})

    out.close()
    exit(0)

# Start cec-client thread
ON_POSIX = 'posix' in sys.builtin_module_names
p = Popen(['cec-client'], stdout=PIPE, stdin=PIPE, bufsize=1, close_fds=ON_POSIX)
q = Queue()
t = Thread(target=cec_thread, args=(p.stdout, q))
t.daemon = True # thread dies with the program
t.start()

#Give cec-client time to start up
time.sleep(5)

global lastNetwork
lastNetwork = time.time()

while True :
    s = socket.socket()         # Create a socket object
    host = MYTH_IP
    port = MYTH_SOCKET                # Reserve a port for your service.
    s.connect((host, port))

    last_net = ""
    while True:
        
        # Handle communication with myth computer
        s.send(" ")
        read = s.recv(1024)

        if "on" in read:
            desiredOn = True
            lastNetwork = time.time()
        elif "off" in read:
            desiredOn = False
            lastNetwork = time.time()

        if last_net != read:
            logger.debug("socket: " + read)
        last_net = read

        # Check for data from cec-client thread
        try:  line = q.get_nowait() # or q.get(timeout=.1)
        except Empty:
            # do nothing
            line = None
        else: # got line
            if line["id"] == "active source":
                current = line["val"]
                if current != activeSource:
                    logger.debug("hdmi <- active input: " + current )
                    activeSource = current

            if line["id"] == "tv power":
                currentlyOn = line["val"]
                logger.debug("hdmi <- TV is" + (" on" if currentlyOn else " off" ))


        # Handle power switching of TV
        if desiredOn and not currentlyOn:
            logger.debug("hdmi -> Turning TV on")
            p.stdin.write("on 0\n")
            time.sleep (3)
            cecGetPowerStatus()

        if not desiredOn and currentlyOn and activeSource == "myth":
            logger.debug("hdmi -> Turning TV off")
            p.stdin.write("standby 0\n")
            time.sleep (3)
            cecGetPowerStatus()


        # Comms has dropped out, let system service manager restart
        if time.time() - lastNetwork > NET_TIMEOUT:
            exit()

        # Pause before next scan
        time.sleep (0.5)

    s.close                     # Close the socket when done
    logHandler.close()

#EOF