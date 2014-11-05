#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket
import sys
import curses.ascii as ascii
import time
import base64
import json
import urllib2
import datetime
import couchdb
import threading
import Queue
PORT = 10001 #Electricity meter port

SOH = "\x01"
STX = "\x02"
ETX = "\x03"
ACK = "\x06"
CR = "\x0D"
LF = "\x0A"

BCC = "\xFF"



PASSWORD = "(ABCDEF)"

couch = None
db = None
s = None

def setup_couchdb(credentials):
   global couch
   global db
   couch = couchdb.Server("%(server)s" % credentials)
   couch.resource.credentials = ('%(user)s' % credentials,"%(passw)s" % credentials)
   db = couch['giraff'] # existing

def setup_socket(address):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = (address, PORT)
    print "Client listening on: ",server_address
    return [s,server_address]

def connect(s,addr):
    s.connect(addr)
    s.setblocking(0)

def prettify(bytes):
    bytes = bytes.replace(SOH,"<SOH>")
    bytes = bytes.replace(STX,"<STX>")
    bytes = bytes.replace(ETX,"<ETX>")
    bytes = bytes.replace(ACK,"<ACK>")
    bytes = bytes.replace(CR,"<CR>")
    bytes = bytes.replace(LF,"<LF>")
    return bytes

def send_without_recv(s,bytes):
    #time.sleep(0.3)
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
    
    
    #print "BCC send: ",bcc," As char: ",chr(bcc)
    if bccStart:       
        bytes.append(str(chr(bcc)))        
        s.sendall(''.join(bytes))
        bytes.pop()
        bytes.append("<BCC>")
    else:
        s.sendall(''.join(bytes))
    data = ''.join(bytes)
    #print "Bytes: ",bytes
    #print "Sending: ",data

    bytes = prettify(data)
    #print >>sys.stderr, 'sending "%s"' % bytes

def send(s,bytes):
    send_without_recv(s,bytes)
    data = recv(s)
    return data

def recv(s):
    bcc = 0
    error = False
    total_data = []
    begin = time.time()
    timeout = 5
    #print "Waiting"
    while True:
        if total_data and time.time()-begin > timeout:
            print "Timeout 1!"
            break
            #raise Exception("Connection timeout")
        elif time.time()-begin > timeout*2:
            print "Timeout 2!"
            break
            #raise Exception("Connection timeout")
        try:
            data = s.recv(4096) 
            #print "Data: ",data
            #for idx,byte in enumerate(bytes):                
            if data:
                total_data.append(data)
                #print "Response time: ",time.time()-begin
                if ord(data[len(data)-2])==ord(ETX):
                    #print "ETXEND!"
                    break
                elif ord(data[len(data)-1])==ord('\n') and ord(data[len(data)-2])==ord('\r'):
                    #print "CRLFEND!"
                    break
                elif ord(data[len(data)-1])==ord(ACK):
                    break
                begin = time.time()
            else:
                time.sleep(0.1)
        except Exception as e:
            pass
    bytes = ''.join(total_data)
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
        #print "Byte: ",byte,"Len: ",len(bytes), "Idx: ",idx
        if idx == len(bytes)-1:
            #print "Breaking"
            break
        if not bccStart and (byte == SOH or byte == STX):
            bccStart = True
            bccreceived = ord(bytes[-1])
        else:
            for char in byte:
                #print "Char: ",ord(char)
                bcc ^=  ord(char)
    return_data = bytes[:-1]
    if(bccStart):
        #print "BCC recv: ",bccreceived
        #print "BCC recv calc: ",bcc
        if(bccreceived == bcc):
            #BCC OK
            parse(bytes)

            bytes = bytes[:-1]
            bytes = ''.join([bytes,"<BCC>"])

        else:
            error = True
    
    prettybytes = prettify(bytes)
    

    if error:
        print >>sys.stderr, 'Warning! BBC not OK: Received "%s"' % prettybytes
    else:
        #print >>sys.stderr, 'Received "%s"' % bytes
        return return_data

    #bytes.append(str(chr(bcc)))
    #print "Bytes: ",bytes
    #print "Sending: ",data    
    #connection.sendall(data)

def parse(bytes):
    #print "Data: ",bytes
    soh = bytes.find(SOH,0,len(bytes))
    start = bytes.find(STX, 0, len(bytes))
    end = bytes.find(ETX, 0, len(bytes))  
    if soh > 0 and start > 0 and end > 0:
        #Got control message with data
        print "Got control data with message"
    elif soh < 0 and start > 0 and end > 0:                   
        print "Got only data message"
    #print "PARSING: ",prettify(bytes)
def ans_to_list(data):
    newstr = data.replace("(","")
    newstr = newstr.replace(")","")
    newstr = newstr.replace(STX,"")
    newstr = newstr.replace(ETX,"")
    newstr = newstr.replace(ACK,"")
    newstr = newstr.replace(SOH,"")
    strlist = newstr.split(",")
    floatlist = []
    for s in strlist:
        floatlist.append(float(s))
    return floatlist

def ans_to_list_str(data):
    newstr = data.replace("(","")
    newstr = newstr.replace(")","")
    newstr = newstr.replace(STX,"")
    newstr = newstr.replace(ETX,"")
    newstr = newstr.replace(ACK,"")
    newstr = newstr.replace(SOH,"")
    strlist = newstr.split(",")
    return strlist

def metertime_to_time(timelist):
    #Should convert ["yyyymmdd","hhmmss"] to
    #linux epoch in milliseconds
    #raise Exception("Not implemented yet!")
    year = int(timelist[0][:4])
    month = int(timelist[0][4:6])
    day = int(timelist[0][6:8])
    hh = int(timelist[1][:2])
    mm = int(timelist[1][2:4])
    ss = int(timelist[1][4:6])
    return unix_time_millis(datetime.datetime(year,month,day,hh,mm,ss))

def unix_time(dt):
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.total_seconds()

def unix_time_millis(dt):
    return unix_time(dt) * 1000.0

def send_to_db2(doc):
    db.save(doc)

def send_to_db(doc, creds):
    url = ('%(server)s/%(db)s' % creds)
    request = urllib2.Request(url, data=json.dumps(doc))
    auth = base64.encodestring('%(user)s:%(passw)s' % creds).replace("\n","")
    request.add_header('Authorization', 'Basic ' + auth)
    request.add_header('Content-Type', 'application/json')
    request.get_method = lambda: 'POST'
    urllib2.urlopen(request, timeout=1)    

def read_data(q,reply_q):
    #print "Running read_data"
    s = q.get()   
    # Send data
    #print "Sending data"

    timeans = send(s,[SOH,"R1",STX,"100C00(1)",ETX])
    metertime =  ans_to_list_str(timeans)
    data1ans = send(s,[SOH,"R1",STX,"100800(1)",ETX])
    data1 =  ans_to_list(data1ans)
    data2ans = send(s,[SOH,"R1",STX,"015200(1)",ETX])
    data2 = ans_to_list(data2ans)
    temp = send(s,[SOH,"R1",STX,"100700(1)",ETX])
    tempdata = ans_to_list(temp)
    print "Got data"
    data = {
        "Meter time":metertime_to_time(metertime),
        "Active energy imp. (Wh)": data1[0],
        "Active energy exp. (Wh)": data1[1],
        "Reactive energy QI (varh)": data1[2],
        "Reactive energy QII (varh)": data1[3],
        "Reactive energy QIII (varh)": data1[4],
        "Reactive energy QIV (varh)": data1[5],
        "Apparent energy imp. (V Ah)": data1[6],
        "Apparent energy exp. (V Ah)": data1[7],
        "Reactive energy imp. (varh)": data1[8],
        "Reactive energy exp. (varh)": data1[9],
        "Reactive energy ind. (varh)": data1[10],
        "Reactive energy cap. (varh)": data1[11],
        "Active energy imp. L1 (Wh)": data1[12],
        "Active energy imp. L2 (Wh)": data1[13],
        "Active energy imp. L3 (Wh)": data1[14],
        "Active energy exp. L1 (Wh)": data1[15],
        "Active energy exp. L2 (Wh)": data1[16],
        "Active energy exp. L3 (Wh)": data1[17],
        "Phase voltage L1 (V)":data2[0],
        "Phase voltage L2 (V)":data2[1],
        "Phase voltage L3 (V)":data2[2],
        "Main voltage L1-L2 (V)":data2[3],
        "Main voltage L2-L3 (V)":data2[4],
        "Main voltage L3-L1 (V)":data2[5],
        "Current L1 (A)":data2[6],
        "Current L2 (A)":data2[7],
        "Current L3 (A)":data2[8],
        "Phase symmetry voltage L1 (rad)":data2[9],
        "Phase symmetry voltage L2 (rad)":data2[10],
        "Phase symmetry voltage L3 (rad)":data2[11],
        "Phase symmetry current L1 (rad)":data2[12],
        "Phase symmetry current L1 (rad)":data2[13],
        "Phase symmetry current L1 (rad)":data2[14],
        "Phase angle L1 (rad)":data2[15],
        "Phase angle L2 (rad)":data2[16],
        "Phase angle L3 (rad)":data2[17],
        "Power factor L1":data2[18],
        "Power factor L2":data2[19],
        "Power factor L3":data2[20],
        "Active power L1 (W)":data2[21],
        "Active power L2 (W)":data2[22],
        "Active power L3 (W)":data2[23],
        "Reactive power L1 (var)":data2[24],
        "Reactive power L2 (var)":data2[25],
        "Reactive power L3 (var)":data2[26],
        "Apparent power L1 (VA)":data2[27],
        "Apparent power L2 (VA)":data2[28],
        "Apparent power L3 (VA)":data2[29],
        "THD Voltage L1 (0.0-1.0)":data2[30],
        "THD Voltage L2 (0.0-1.0)":data2[31],
        "THD Voltage L3 (0.0-1.0)":data2[32],
        "THD Current L1 (0.0-1.0)":data2[33],
        "THD Current L2 (0.0-1.0)":data2[34],
        "THD Current L3 (0.0-1.0)":data2[35],
        "Total active power (W)":data2[36],
        "Total reactive power (var)":data2[37],
        "Total apparent power (VA)":data2[38],
        "Total power factor":data2[39],
        "Total phase angle":data2[40],
        "Frequency":data2[41],
        "VT ratio":data2[42],
        "CT ratio":data2[43],
        "Secondary nominal voltage (V)":data2[44],
        "Secondary nominal current (A)":data2[45],
        "Temperature (C)":tempdata[0]
    }
    reply_q.put([s,data])
    q.task_done()

def main():

    passw = ""
    user = ""
    url = ""

    #There is got to be a text file named ".credentials" in the same folder as the
    #pythons script, containg: <user>,<passw>,<url_to_database>
    #example: user1,password1,https://domain/database
    with open('.credentials', 'r') as f:
        file_data = f.read()
        #print read_data
        creds = file_data.split(',')
        user = creds[0]
        passw = creds[1]
        url = creds[2]
        db = creds[3].replace('\n','')


    credentials = {
      'user': user,
      'passw': passw,
      'server': url,
      'db': db
    }

    #print credentials
    setup_couchdb(credentials)
    addr_q = Queue.Queue()
    reply_q = Queue.Queue()

    #address = q.get()

    socketlist = setup_socket("192.168.1.3")
    s1 = socketlist[0]
    connect(s1,socketlist[1])

    socketlist = setup_socket("192.168.1.4")
    s2 = socketlist[0]
    connect(s2,socketlist[1])

    send(s1,'/?!\r\n')
    send(s1,[ACK,"051\r\n"]) #050 Data readout,#051 programming mode
    send(s1,[SOH,"P2",STX,"(AAAAAA)",ETX]) #<SOH>P2<STX>(ABCDEF)<ETX><BCC>

    send(s2,'/?!\r\n')
    send(s2,[ACK,"051\r\n"]) #050 Data readout,#051 programming mode
    send(s2,[SOH,"P2",STX,"(AAAAAA)",ETX]) #<SOH>P2<STX>(ABCDEF)<ETX><BCC>


    try:
        while True:
            thread1 = threading.Thread(target=read_data,args=(addr_q,reply_q,))
            thread2 = threading.Thread(target=read_data,args=(addr_q,reply_q,))
            thread1.daemon = True
            thread2.daemon = True
            thread1.start()
            thread2.start()


            print "Adding to queue"
            addr_q.put(s1)
            print "Adding to queue"
            addr_q.put(s2)
            print "Waiting"
            addr_q.join()
            print "Parsing"
            first = reply_q.get(block=True)
            print "Got 1st"
            second = reply_q.get(block=True)
            print "Got 2nd"

            print first
            print second
        #if first[0] == "192.168.1.3":
        #    wind = first[1]
        #    solar = second[1]
        #else:
        #    wind = second[1]
        #    solar = first[1]

        #try:
        #    data = {
        #        "wind":wind,
        #        "solar":solar,
        #        "timestamp":int(time.time()*1000)
        #    }
        #    send_to_db2(data)

            #send('END') 
            print "Done."
    finally:
        send_without_recv(s1,[SOH,"B0",ETX])
        send_without_recv(s2,[SOH,"B0",ETX])
        s1.close()
        s2.close()
            #return
            #print >>sys.stderr, 'closing socket'
            #s.close()

if __name__ == "__main__":
    main()
