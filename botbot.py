#!/usr/bin/env python
"""
                            _.:` botbot `:._

This is a script which imports the botbot module and starts the botbot client

"""
import difflib
import re
import sys
import time
import traceback

from multiprocessing import Process

from botbot.bot import Bot
from botbot.conf import (CHANNEL,
                         DEBUG,
                         HOSTNAME,
                         PING_INTERVAL,
                         PORT,
                         REALNAME,
                         RETRY_INTERVAL,
                         SERVER,
                         SERVERNAME,
                         USERNAME)
from botbot.debug import debug
from botbot.definitions import IRC_DEFINITIONS, CUST_DEFINITIONS
from botbot.parser import Parser


B = None

IRC_PARSER = None
CUST_PARSER = None


def connect(host, port, chan):
    """Connect to IRC host, on port, and join chan"""
    debug('Connecting to server {}:{} and joining {}'.format(
            host, port, chan))
    global B
    global IRC_PARSER
    global CUST_PARSER
    B = Bot(host, int(port), debug=DEBUG)
    IRC_PARSER = Parser(B, chan, IRC_DEFINITIONS)
    CUST_PARSER = Parser(B, chan, CUST_DEFINITIONS)
    B.write('NICK {}\r\n'.format(USERNAME))
    B.write('USER {} {} {} :{}\r\n'.format(
                USERNAME, HOSTNAME, SERVERNAME, REALNAME))
    # TODO: Figure out a safe solution for this
    time.sleep(3)
    B.write('JOIN {}\r\n'.format(chan))

def disconnect():
    """Part from IRC channel and disconnect from host"""
    try:
        B.write('DISCONNECT\r\n')
        B.close()
    except:
        e = traceback.format_exc()
        debug(e, log_only=True)

def pinger(host):
    """Ping the IRC server at the given interval until a keyboard interrupt"""
    # multiprocessing not threading.
    while True:
        try:
            time.sleep(PING_INTERVAL)
            B.write('PING {}\r\n'.format(host))
        except KeyboardInterrupt:
            break
        except:
            e = traceback.format_exc()
            debug(e)
            break

def recover(args):
    """Recover from a fatal error"""
    retry = RETRY_INTERVAL
    while True:
        try:
            disconnect()
            time.sleep(retry)
            connect(*args)
            Process(target=pinger, args=(SERVER,)).start()
            break
        except KeyboardInterrupt:
            break
        except:
            e = traceback.format_exc()
            debug(e)
            retry *= 2

def irc_parse(line):
    """Parse IRC protocol message such as PING, ERROR, NETSPLIT, etc."""
    IRC_PARSER.parse(line)

def cust_parse(line):
    """Parse custom bot commands via PM and channel."""
    CUST_PARSER.parse(line)

def parse(lines):
    """Create a thread for each parser the lines need to run through"""
    for line in lines:
        Process(target=irc_parse, args=(line,)).start()
        Process(target=cust_parse, args=(line,)).start()


if __name__ == '__main__':
    # Connect to the server
    argc = len(sys.argv)
    args = None
    if argc == 4:
        args = (sys.argv[1], sys.argv[2], sys.argv[3])
    elif argc == 3:
        args = (sys.argv[1], sys.argv[2], CHANNEL)
    elif argc == 2:
        if sys.argv[1] in ('-help', '--help'):
            debug('Usage:\n\n$ botbot\n$ botbot <host>\n$ botbot <host>' +
                  ' <port>\n$ botbot <host> <port> <channel>', prefix=False)
            sys.exit(1)
        else:
            args = (sys.argv[1], PORT, CHANNEL)
    elif argc == 1:
        args = (SERVER, PORT, CHANNEL)
    connect(*args)
    debug('welcome')

    # Create a process to ping the server every so often. This allows us to
    # stay connected to the server even if the socket receives no pings. This
    # arises if the client side network is cleaning up tcp connections before
    # the server can ping the client.
    Process(target=pinger, args=(SERVER,)).start()

    # Loop until keyboard interrupt
    msg = ''
    while True:
        try:
            msg += B.read()
            if not msg:
                raise Exception('Socket Error: Read returned empty string.')
            lines = msg.split('\r\n')
            msg = lines.pop()
            # Create a new thread for parsing so we can read again
            Process(target=parse, args=(lines,)).start()
        except KeyboardInterrupt:
            disconnect()
            debug('\nGoodbye')
            sys.exit(0)
        except:
            e = traceback.format_exc()
            debug(e)
            debug('\n\nFATAL ERROR\n\nAttempting recovery...')
            recover(args)
