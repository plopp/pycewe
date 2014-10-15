#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket
import sys
import array
from binascii import unhexlify, hexlify
SOH = '\x01'
STX = '\x02'
ETX = '\x03'

ACK = '\x06'

BCC = "\xFF"

PORT = 10000
s = ""

PASSWORD = "(ABCDEF)"

def setup_socket():
    global s
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = ('localhost', PORT)
    s.bind(server_address)
    print "Server set up on: ",server_address
def listen():
    s.listen(1)

def send(connection,bytes):
    if bytes == "END":
        connection.sendall("END")
        return
    if bytes == [0]:
        connection.sendall("0")
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
        bytes.pop()
        bytes.append(str(unichr(bcc)))
    data = ''.join(bytes)
    #print "Bytes: ",bytes
    #print "Sending: ",data    
    connection.sendall(data)

def checkPassword(passwd):  
    if passwd == PASSWORD:
        return True
    else:
        return False

def main():
    setup_socket()
    listen()
    while True:
        #print "Waiting for a connection..."
        connection, client_address = s.accept()
        try:
            print "Connection from: ",client_address
            while True:
                print "Waiting for data"
                try:
                    data=connection.recv(32)
                except:
                    break                    
                #print "Received lengt: ",len(data)
                if data=="/?!\r\n":
                    connection.sendall("/CWI6135701\r\n")
                elif data==''.join(["\x06","061\r\n"]):
                    send(connection,[SOH,"P0",STX,"(xxxx)",ETX,BCC])
                    #print "Done"
                elif data.startswith(''.join([SOH,"P2",STX])):                    
                    start = data.find(STX, 0, len(data))
                    end = data.find(ETX, 0, len(data))                    
                    if checkPassword(data[start+1:end]):
                        print "Supplied password: ",data[start:end]
                        send(connection,["ACK"])
                    else:
                        send(connection,[SOH,"B0",ETX,BCC]) #<SOH>B0<ETX><BCC>
                        continue
                elif len(data)==3 and data == "END":
                    send(connection,"END")
                    print "No more data from ",client_address,"."
                    break
                else:
                    break
                    #connection.sendall("Unknown command")
                #print "While done"
        finally:
            print "Closing socket"
            connection.close()

if __name__ == "__main__":
    main()
