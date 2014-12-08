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
from pymodbus.client.sync import ModbusSerialClient as Modbus
from socket import gethostbyname, gaierror
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

timeoutModbus = 0.1
portName = '/dev/ttyUSB0'
Pyro = Modbus(method='rtu', port=portName, baudrate=38400, timeout=timeoutModbus, stopbits = 1, parity = 'E')


def setup_couchdb(credentials):
   global couch
   global db
   couch = couchdb.Server("https://%(domain)s" % credentials)
   couch.resource.credentials = ('%(user)s' % credentials,"%(passw)s" % credentials)
   try:
       db = couch['%(db)s' % credentials] # existing
   except:
       return False
   return True

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

def send_to_db2(q,credentials):
    size = q.qsize()
    if size>10:
        print "Queue size is 10, sending"
        doc_arr = []
        for i in range(0,size):
            doc = q.get()
            doc_arr.append(doc)
            q.task_done()
        db.update(doc_arr)
        couch.replicate("%(db)s" % credentials,"https://%(user)s:%(passw)s@%(domain)s/%(repldb)s" % credentials)

def send_to_db(doc, creds):
    url = ('https://%(domain)s/%(db)s' % creds)
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
    print "Sending data"

    timeans = send(s,[SOH,"R1",STX,"100C00(1)",ETX])
    metertime =  ans_to_list_str(timeans)
    data1ans = send(s,[SOH,"R1",STX,"100800(1)",ETX])
    data1 =  ans_to_list(data1ans)
    data2ans = send(s,[SOH,"R1",STX,"015200(1)",ETX])
    data2 = ans_to_list(data2ans)
    temp = send(s,[SOH,"R1",STX,"100700(1)",ETX])
    tempdata = ans_to_list(temp)
    data = {
        "meter_time":metertime_to_time(metertime),
        #"act_ener_imp": data1[0], #Wh
        #"act_ener_exp": data1[1], #Wh
        #"rea_ener_q1": data1[2], #varh
        #"rea_ener_q2": data1[3], #varh
        #"rea_ener_q3": data1[4], #varh
        #"rea_ener_q4": data1[5], #varh
        #"app_ener_imp": data1[6], #V Ah
        #"app_ener_exp": data1[7], #V Ah
        #"rea_ener_imp": data1[8], #varh
        #"rea_ener_exp": data1[9], #varh
        #"rea_ener_ind": data1[10], #varh
        #"rea_ener_cap": data1[11], #varh
        "act_ener_imp_L1": data1[12], #Wh
        "act_ener_imp_L2": data1[13], #Wh
        "act_ener_imp_L3": data1[14], #Wh
        "act_ener_exp_L1": data1[15], #Wh
        "act_ener_exp_L2": data1[16], #Wh
        "act_ener_exp_L3": data1[17], #Wh
        #"pha_volt_L1":data2[0], #V
        #"pha_volt_L2":data2[1], #V
        #"pha_volt_L3":data2[2], #V
        #"main_volt_L1_L2":data2[3], #V
        #"main_volt_L2_L3":data2[4], #V
        #"main_volt_L3_L1":data2[5], #V
        "current_L1":data2[6], #A
        "current_L2":data2[7], #A
        "current_L3":data2[8], #A
        #"pha_sym_volt_L1":data2[9], #rad
        #"pha_sym_volt_L2":data2[10], #rad
        #"pha_sym_volt_L3":data2[11], #rad
        #"pha_sym_current_L1":data2[12], #rad
        #"pha_sym_current_L2":data2[13], #rad
        #"pha_sym_current_L3":data2[14], #rad
        #"pha_angle_L1":data2[15], #rad
        #"pha_angle_L2":data2[16], #rad
        #"pha_angle_L3":data2[17], #rad
        "pow_fact_L1":data2[18], 
        "pow_fact_L2":data2[19],
        "pow_fact_L3":data2[20],
        "act_pow_L1":data2[21], #W
        "act_pow_L2":data2[22], #W
        "act_pow_L3":data2[23], #W
        #"rea_pow_L1":data2[24], #var
        #"rea_pow_L2":data2[25], #var
        #"rea_pow_L3":data2[26], #var
        #"app_pow_L1":data2[27], #VA
        #"app_pow_L2":data2[28], #VA
        #"app_pow_L3":data2[29], #VA
        #"thd_volt_L1":data2[30],
        #"thd_volt_L2":data2[31],
        #"thd_volt_L3":data2[32],
        #"thd_cur_L1":data2[33],
        #"thd_cur_L2":data2[34],
        #"thd_cur_L3":data2[35],
        "tot_act_power":data2[36], #W
        #"tot_rea_power":data2[37], #var
        #"tot_app_power":data2[38], #VA
        "tot_pow_fact":data2[39],
        #"tot_pha_angle":data2[40],
        "frequency":data2[41], #Hz
        #"vt_ratio":data2[42],
        "ct_ratio":data2[43],
        #"sec_nom_volt":data2[44], #V
        #"sec_nom_cur":data2[45], #A
        "temperature":tempdata[0] #C
    }
    if s.getpeername()[0] == "192.168.1.3":
        reply_q.put(["solar",data])
    elif s.getpeername()[0] == "192.168.1.4":
        reply_q.put(["wind",data])
    q.task_done()

def read_modbus_pyro(q,reply_q):
    reg = q.get()
    data = {}
    
    for r in reg:
        ans = Pyro.read_input_registers(r, 1, unit=1)
        if r == 5:
            data["radiance"] = ans.registers[0]/10.0
        if r == 8:        
            data["temp"] = ans.registers[0]/10.0
    reply_q.put(["pyro",data])
    q.task_done()

def main():
    passw = ""
    user = ""
    url = ""

    #There is got to be a text file named ".credentials" in the same folder as the
    #python script, containg: <user>,<passw>,<domain>,<repldb_name>,<dbname>
    #example: user1,password1,domain,database-repl,database
    try:
        with open('.credentials', 'r') as f:
            file_data = f.read()
            #print read_data
            creds = file_data.split(',')
            user = creds[0]
            passw = creds[1]
            domain = creds[2]
            repldb = creds[3]
            dbname = creds[4].replace('\n','')
    except:
        print "Error opening credentials file."
        raise

    credentials = {
      'user': user,
      'passw': passw,
      'domain': domain,
      'repldb': repldb,
      'db': dbname
    }
    print credentials
    #print credentials
    while not setup_couchdb(credentials):
        print "Could not connect to database. Retrying soon..."
        time.sleep(2)
        

    addr_q = Queue.Queue()
    reply_q = Queue.Queue()
    send_q = Queue.Queue()
    register_q = Queue.Queue()    
    

    socketlist = setup_socket("192.168.1.3")
    s1 = socketlist[0]
    try:
        connect(s1,socketlist[1])
    except:
        print "Could not connect to 192.168.1.3"
        raise

    socketlist = setup_socket("192.168.1.4")
    s2 = socketlist[0]

    try:
        connect(s2,socketlist[1])
    except:
        print "Could not connect to 192.168.1.4"
        raise
    
    send(s1,'/?!\r\n')
    send(s1,[ACK,"051\r\n"]) #050 Data readout,#051 programming mode
    send(s1,[SOH,"P2",STX,"(AAAAAA)",ETX]) #<SOH>P2<STX>(ABCDEF)<ETX><BCC>

    send(s2,'/?!\r\n')
    send(s2,[ACK,"051\r\n"]) #050 Data readout,#051 programming mode
    send(s2,[SOH,"P2",STX,"(AAAAAA)",ETX]) #<SOH>P2<STX>(ABCDEF)<ETX><BCC>

    times = []



    try:
        while True:
            t0 = time.time()
            thread1 = threading.Thread(target=read_data,args=(addr_q,reply_q,))
            thread2 = threading.Thread(target=read_data,args=(addr_q,reply_q,))
            thread3 = threading.Thread(target=send_to_db2,args=(send_q,credentials,))
            thread4 = threading.Thread(target=read_modbus_pyro,args=(register_q,reply_q,))
            thread1.daemon = True
            thread2.daemon = True
            thread3.daemon = True
            thread4.daemon = True
            thread1.start()
            thread2.start()
            thread3.start()
            thread4.start()

            addr_q.put(s1)
            addr_q.put(s2)
            register_q.put([5,8])

            print "Threads running"
            addr_q.join()
            register_q.join()
            print "Reply queue size: ", reply_q.qsize()
            ansarr = []
            print "Threads joined"            
            ansarr.append(reply_q.get(block=True))
            print "Read first",ansarr
            ansarr.append(reply_q.get(block=True))
            print "Read second",ansarr[1]
            ansarr.append(reply_q.get(block=True))
            print "Read thirds",ansarr[2]
            print "Reading reply_q"
            for post in ansarr:
                if post[0] == "wind":
                    wind = post[1]
                elif post[0] == "solar":
                    solar = post[1]
                elif post[0] == "pyro":
                    pyro = post[1]

            data = {
                "wind":wind,
                "solar":solar,
                "pyro":pyro,
                "timestamp":int(time.time()*1000)
            }
            print data
            send_q.put(data)
            t1 = time.time()
            total = t1-t0
            if (1-total)>0.05:
                time.sleep(1-total)
            now = time.time()
            times.append(now-t0)
            print ".",
            #send_to_db2(data)

            #send('END') 
    finally:
        send_without_recv(s1,[SOH,"B0",ETX])
        send_without_recv(s2,[SOH,"B0",ETX])
        s1.close()
        s2.close()
        Pyro.close()

        sum = 0
        for i in times:
            sum+=i
        if len(times)>0:
            print "Avg: ",sum/len(times)
            #return
            #print >>sys.stderr, 'closing socket'
            #s.close()

if __name__ == "__main__":
    while True:
        try:
            main()
        except:
            print "Error, retrying in 10 seconds"
            time.sleep(10)
            pass
