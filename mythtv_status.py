#!/usr/bin/python

import socket

MYTH_IP = "127.0.0.1"
MYTH_SOCKET = 6546

QUERY_COMMAND = "query location\n"

# Example Playing
# 'Playback Recorded 0:26:56 of 1:17:27 1x 1010 2014-06-05T08:28:00Z 40405 /myth/drive_wd2/tv/1010_20140605082800.mpg 25 Subtitles: *0:[None]* 1:[TT CC 1: English]\r\n# '

# Example Paused
# 'Playback Recorded 0:27:07 of 1:17:27 pause 1010 2014-06-05T08:28:00Z 40678 /myth/drive_wd2/tv/1010_20140605082800.mpg 25 Subtitles: *0:[None]* 1:[TT CC 1: English]\r\n# '

class mythtv_status(object):
    def __init__(self):
        self.connect()

    def connect(self):
        self.s = socket.socket()         # Create a socket object
        self.host = MYTH_IP
        self.port = MYTH_SOCKET                # Reserve a port for your service.
        self.s.connect((self.host, self.port))
        self.s.settimeout(1.0)

    def getStatus(self,verbose = False):
        status = False

        try:
            #s = socket.socket()         # Create a socket object
            #host = MYTH_IP
            #port = MYTH_SOCKET                # Reserve a port for your service.
            #s.connect((host, port))
            #s.settimeout(1.0)

            read = ""
            try:
                read = self.s.recv(1024)
            except socket.timeout:
                pass

            self.s.send(QUERY_COMMAND)
            try:
                read = self.s.recv(1024)
            except socket.timeout:
                pass

            tokens = read.split(" ")
            if len(tokens):
                playing = False
                if len(tokens) == 2 and verbose:
                    print "Currently on screen: %s" % (tokens[0].replace("\r\n#",""))

                if len(tokens) > 2:
                    if verbose:
                        print "Currently on screen: %s" % (tokens[0])
                    state = tokens[5]
                    if "pause" not in state:
                        playing = True

                if verbose:
                    print tokens[9]
                    print "playing" if playing else "not playing"

                status = playing
        except socket.error:
            try:
                self.connect()
            except socket.error:
                pass

            if verbose:
                print "Can't connect to myth control port"
            status = None

        return status

if __name__ == "__main__":
    status = mythtv_status()
    status.getStatus(verbose = True)