#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket
import sys
import curses.ascii as ascii

PORT = 10001
ADDRESS = "192.168.0.46"

SOH = "\x01"
STX = "\x02"
ETX = "\x03"
ACK = "\x06"
CR = "\x0D"
LF = "\x0A"

BCC = "\xFF"


server_address = ""
s = ""

PASSWORD = "(ABCDEF)"

def setup_socket():
    global s,server_address
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (ADDRESS, PORT)
    print "Client listening on: ",server_address
def connect():
    s.connect(server_address)

def prettify(bytes):
    bytes = bytes.replace(SOH,"<SOH>")
    bytes = bytes.replace(STX,"<STX>")
    bytes = bytes.replace(ETX,"<ETX>")
    bytes = bytes.replace(ACK,"<ACK>")
    bytes = bytes.replace(CR,"<CR>")
    bytes = bytes.replace(LF,"<LF>")
    return bytes

def send(bytes):
    if bytes == "END":
        s.sendall("END")
        return
    bccStart = False
    bcc = 0
    #print "Bytes: ",bytes
    for byte in bytes:
        #print "Byte: ",byte
        if not bccStart and (byte == SOH or byte == STX):
            bccStart = True
        elif not byte==BCC:
            for char in byte:
                #print "Char: ",ord(char)
                bcc ^=  ord(char)
    
    
    #print "BCC: ",bcc
    if bccStart:        
        bytes.append(str(unichr(bcc)))        
        s.sendall(''.join(bytes))
        bytes.pop()
        bytes.append("<BCC>")
    else:
        s.sendall(''.join(bytes))
    data = ''.join(bytes)
    #print "Bytes: ",bytes
    #print "Sending: ",data

    bytes = prettify(data)
    print >>sys.stderr, 'sending "%s"' % bytes
    recv()

def recv():
    bcc = 0
    error = False
    bytes = s.recv(128) 
    if bytes == "END":
        #print "END received."
        return
    elif bytes.find("B0")>0:
        raise Exception("Meter closed connection, wrong password?")
    #    connection.sendall("END")
    #    return
    bccStart = False
    bccreceived = 0
    #print "Bytes: ",bytes
    for idx,byte in enumerate(bytes):
        #print "Byte: ",byte
        if idx == len(
bytes)-1:
            break
        if not bccStart and (byte == SOH or byte == STX):
            bccStart = True
            bccreceived = ord(bytes[-1])
            #bytes = bytes[:-1]
            #print bytes
            #print "BCC recv: ",bccreceived
        else:
            for char in byte:
                #print "Char: ",ord(char)
                bcc ^=  ord(char)
    
    #print "BCC calc: ",bcc
    if(bccStart):
        if(bccreceived == bcc):
            #BCC OK
            parse(bytes)

            bytes = bytes[:-1]
            bytes = ''.join([bytes,"<BBC>"])

        else:
            error = True
    
    bytes = prettify(bytes)
    

    if error:
        print >>sys.stderr, 'Warning! BBC not OK: Received "%s"' % bytes
    else:
        print >>sys.stderr, 'Received "%s"' % bytes
    #bytes.append(str(unichr(bcc)))
    #print "Bytes: ",bytes
    #print "Sending: ",data    
    #connection.sendall(data)

def parse(bytes):
    print "Data: ",bytes
    soh = bytes.find(SOH,0,len(bytes))
    start = bytes.find(STX, 0, len(bytes))
    end = bytes.find(ETX, 0, len(bytes))  
    if soh > 0 and start > 0 and end > 0:
        #Got control message with data
        print "Got control data with message"
    elif soh < 0 and start > 0 and end > 0:                   
        print "Got only data message"
    print "PARSING: ",prettify(bytes)

def main():
    setup_socket()
    connect()
    try:    
        # Send data
        send('/?!\r\n')
        #send([ACK,"061\r\n"])
        #send([SOH,"P2",STX,PASSWORD,ETX]) #<SOH>P2<STX>(ABCDEF)<ETX><BCC>
        #send([SOH,"R1",STX,"108700(1)",ETX])
        #send('END') 
    finally:
        print >>sys.stderr, 'closing socket'
        s.close()

if __name__ == "__main__":
    main()
