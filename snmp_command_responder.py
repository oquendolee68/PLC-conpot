# Command Responder (GET/GETNEXT)
# Based on examples from http://pysnmp.sourceforge.net/

from pysnmp.entity import config
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.carrier.asynsock.dgram import udp

import gevent
from gevent import socket

from modules.udp_server import DatagramServer
from modules import snmp_engine as engine

import config as conpot_config


class SNMPDispatcher(DatagramServer):

    def __init__(self):
        pass

    def handle(self, msg, address):
        print repr(msg), address

    def registerTransport(self, tDomain, transport):
        DatagramServer.__init__(self, transport, self.handle)

    def registerRecvCbFun(self, recvCbFun):
        print "recvCbFun", recvCbFun

    def registerTimerCbFun(self, timerCbFun, tickInterval=None):
        print "timerCbFun", timerCbFun

    def sendMessage(self, outgoingMessage, transportDomain, transportAddress):
        print outgoingMessage, transportDomain, transportAddress


class CommandResponder(object):

    def addSocketTransport(self, snmpEngine, transportDomain, transport):
        """Add transport object to socket dispatcher of snmpEngine"""
        if not snmpEngine.transportDispatcher:
            snmpEngine.registerTransportDispatcher(SNMPDispatcher())
        snmpEngine.transportDispatcher.registerTransport(transportDomain, transport)

    def __init__(self):
        # Create SNMP engine
        self.snmpEngine = engine.SnmpEngine()
        # Transport setup

        udp_sock = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_DGRAM)
        udp_sock.setsockopt(gevent.socket.SOL_SOCKET, gevent.socket.SO_BROADCAST, 1)
        udp_sock.bind((conpot_config.snmp_host, conpot_config.snmp_port))
        # UDP over IPv4
        self.addSocketTransport(
            self.snmpEngine,
            udp.domainName,
            udp_sock
        )

        # SNMPv3/USM setup

        # user: usr-md5-des, auth: MD5, priv DES
        config.addV3User(
            self.snmpEngine, 'usr-md5-des',
            config.usmHMACMD5AuthProtocol, 'authkey1',
            config.usmDESPrivProtocol, 'privkey1'
        )
        # user: usr-sha-none, auth: SHA, priv NONE
        config.addV3User(
            self.snmpEngine, 'usr-sha-none',
            config.usmHMACSHAAuthProtocol, 'authkey1'
        )
        # user: usr-sha-aes128, auth: SHA, priv AES/128
        config.addV3User(
            self.snmpEngine, 'usr-sha-aes128',
            config.usmHMACSHAAuthProtocol, 'authkey1',
            config.usmAesCfb128Protocol, 'privkey1'
        )

        # Allow full MIB access for each user at VACM
        config.addVacmUser(self.snmpEngine, 3, 'usr-md5-des', 'authPriv',
                           (1, 3, 6, 1, 2, 1), (1, 3, 6, 1, 2, 1))
        config.addVacmUser(self.snmpEngine, 3, 'usr-sha-none', 'authNoPriv',
                           (1, 3, 6, 1, 2, 1), (1, 3, 6, 1, 2, 1))
        config.addVacmUser(self.snmpEngine, 3, 'usr-sha-aes128', 'authPriv',
                           (1, 3, 6, 1, 2, 1), (1, 3, 6, 1, 2, 1))

        # Get default SNMP context this SNMP engine serves
        snmpContext = context.SnmpContext(self.snmpEngine)

        # Register SNMP Applications at the SNMP engine for particular SNMP context
        cmdrsp.GetCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.SetCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.NextCommandResponder(self.snmpEngine, snmpContext)
        cmdrsp.BulkCommandResponder(self.snmpEngine, snmpContext)


if __name__ == "__main__":
    server = CommandResponder()
    print 'Starting echo server on port 161'
    server.snmpEngine.transportDispatcher.serve_forever()