#!/usr/bin/env python

import sys
from subprocess import PIPE, Popen, check_output, CalledProcessError
from threading  import Thread
import time
import socket

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x

import logging
import logging.handlers

import zmq

from tinyrpc.protocols.jsonrpc import JSONRPCProtocol
from tinyrpc.transports.zmq import ZmqServerTransport
from tinyrpc.server import RPCServer
from tinyrpc.dispatch import RPCDispatcher
import tinyrpc.dispatch


CEC_DEBUG = True

#MYTH_IP = "192.168.0.9"
#MYTH_SOCKET = 55555
SERVIER_ADDR = "tcp://192.168.0.6:6601"

#LOG_PATH='/home/corona/tv_suspend.log'
NET_TIMEOUT = 11 * 60 #seconds

#logging
FORMAT="%(asctime)-15s : %(message)s"
#logHandler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=2*1024*1024, backupCount=2)
logHandler = logging.StreamHandler(sys.stdout)
logHandler.setFormatter(logging.Formatter(FORMAT))
logger = logging.getLogger('log')
logger.setLevel(logging.DEBUG)
logger.addHandler(logHandler)

logger.debug("Startup")

# Holds current internal representation of active tv input source
global expectActiveSource
expectActiveSource = None

class CecPowerControl(object):
    def __init__(self, statusQueue):
        """
        @type statusQueue: Queue()
        """
        self._statusQueue = statusQueue

    @tinyrpc.dispatch.public
    def SetPowerStatus(self, on):
        """
        @type on: bool
        """
        self._statusQueue.put("on" if on else "off")
        log = "Received: %s" % str(on)
        logger.debug(log)
        return log


def cec_client_cleanup():
    try:
        pids = check_output(["pgrep", "-f", "cec-client"])
        for pid in pids.split("\n"):
            if pid:
                logger.debug("Killing existing cec-client: %s" % pid)
                Popen(["kill", "-9", pid])
    except CalledProcessError as ex:
        pass

def cecGetPowerStatus(cec_client):
    cec_client.stdin.write("pow 0.0.0.0\n") # get current power status

def cecGetActiveSource(cec_client):
    global expectActiveSource
    expectActiveSource = time.time()
    cec_client.stdin.write("tx 1f:85\n") # get current power status

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

def network_server(statusQueue):
    cec_power_control=CecPowerControl(statusQueue)

    ctx = zmq.Context()
    dispatcher = RPCDispatcher()
    transport = ZmqServerTransport.create(ctx, SERVIER_ADDR)

    rpc_server = RPCServer(
        transport,
        JSONRPCProtocol(),
        dispatcher
    )

    dispatcher.register_instance(cec_power_control, 'tv_controller.')

    logger.debug("Starting RPC Server")
    rpc_server.serve_forever()


def main():

    cec_client_cleanup()

    # Start cec-client thread
    ON_POSIX = 'posix' in sys.builtin_module_names
    cec_client = Popen(['cec-client'], stdout=PIPE, stdin=PIPE, bufsize=1, close_fds=ON_POSIX)
    q = Queue()
    t = Thread(target=cec_thread, args=(cec_client.stdout, q))
    t.daemon = True # thread dies with the program
    t.start()

    #Give cec-client time to start up
    time.sleep(5)

    statusQueue = Queue()

    nt = Thread(target=network_server, args=(statusQueue,))
    nt.daemon = True # thread dies with the program
    nt.start()

    # daemon=Pyro4.Daemon()                                   # make a Pyro daemon
    # ns=Pyro4.locateNS()                                     # find the name server
    # uri=daemon.register(cec_power_control)                  # register the object as a Pyro object
    # ns.register("tv_controller.cec_power_control", uri)     # register the object with a name in the name server
    #
    # daemon.requestLoop()                                    # start the event loop of the server to wait for calls
    #

    # global lastNetwork
    # lastNetwork = time.time()

    # local state variables
    activeSource = "myth"
    desiredOn = True
    currentlyOn = False

    while True :
        # s = socket.socket()         # Create a socket object
        # host = MYTH_IP
        # port = MYTH_SOCKET                # Reserve a port for your service.
        # s.connect((host, port))

        last_net = ""
        while True:

            # Handle communication with myth computer
            # s.send(" ")
            # read = s.recv(1024)
            #
            # if "on" in read:
            #     desiredOn = True
            #     lastNetwork = time.time()
            # elif "off" in read:
            #     desiredOn = False
            #     lastNetwork = time.time()
            #
            # if last_net != read:
            #     logger.debug("socket: " + read)
            # last_net = read

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

            if not statusQueue.empty():
                status = statusQueue.get()
                if "on" in status:
                    desiredOn = True
                    lastNetwork = time.time()
                elif "off" in status:
                    desiredOn = False
                    lastNetwork = time.time()

            # Handle power switching of TV
            if desiredOn and not currentlyOn:
                logger.debug("hdmi -> Turning TV on")
                cec_client.stdin.write("on 0\n")
                time.sleep (3)
                cecGetPowerStatus(cec_client)

            if not desiredOn and currentlyOn:# and activeSource == "myth":
                logger.debug("hdmi -> Turning TV off")
                cec_client.stdin.write("standby 0\n")
                time.sleep (3)
                cecGetPowerStatus(cec_client)


            # Comms has dropped out, let system service manager restart
            # if time.time() - lastNetwork > NET_TIMEOUT:
            #     exit()

            # Pause before next scan
            time.sleep (0.5)

        #s.close                     # Close the socket when done
        logHandler.close()


if __name__ == "__main__":
    main()

#EOF