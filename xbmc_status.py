#!/usr/bin/python

import os
import signal
import subprocess
from xbmcjson import XBMC, PLAYER_VIDEO

class Timeout(Exception):
        pass

def raise_timeout(self, *args):
    raise Timeout()

def getStatus(verbose = False):
    status = False

    try:
        signal.signal(signal.SIGALRM, raise_timeout)
        signal.alarm(2)

        xbmc = XBMC("http://localhost:8090/jsonrpc", "corona", "diskdisk")

        id = xbmc.Player.GetActivePlayers()["result"][0]["playerid"]
        playing = int(xbmc.Player.GetProperties({'playerid': id, 'properties':['speed']})["result"]["speed"])
        if verbose:
            print "playing" if playing else "not playing"
        status = True if playing else False

    except Exception as e:
        if verbose:
            print "Error reading xbmc status"

    finally:
        signal.alarm(0) #cancel alarm

    return status

if __name__ == "__main__":
    getStatus(verbose = True)