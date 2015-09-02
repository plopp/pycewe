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
import struct
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

def sampleToFile(doc):
    while True:
        try:
            f = open('/mnt/ramdisk/out.json','w+')
            f.write(doc)
            f.close()
            break
        except IOError:
            time.sleep(0.01)


PASSWORD = "(ABCDEF)"

couchlocal = None
dblocal = None
s = None

timeoutModbus = 0.1
portName = '/dev/ttyUSB0'
Pyro = Modbus(method='rtu', port=portName, baudrate=38400, timeout=timeoutModbus, stopbits = 1, parity = 'E')


def setup_couchdb_local(credentials):
   global couchlocal
   global dblocal
   print "Using credentials: ",credentials
   couchlocal = couchdb.Server("%(protocol)s://%(domain)s" % credentials)
   couchlocal.resource.credentials = ('%(user)s' % credentials,"%(passw)s" % credentials)
   try:
       dblocal = couchlocal['%(db)s' % credentials] # existing
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
    #print "Tx: ",bytes
    data = recv(s)
    return data

def recv(s):
    bcc = 0
    error = False
    total_data = []
    begin = time.time()
    timeout = 5
    name = s.getpeername()[0]
    waitForBcc = False
    #print "Waiting",name
    while True:
        if len(total_data) > 0 and (time.time()-begin) > timeout:
            print "Timeout 1! ***********************************************",name
            #break
            raise Exception("Connection timeout")
        elif (time.time()-begin) > timeout*2:
            print "Timeout 2!",name
            #break
            raise Exception("Connection timeout")
        try:
            data = s.recv(4096) 
            #print "Rx: ",prettify(data),name
            #for idx,byte in enumerate(bytes):                
            #    print "SPLIT: ",ord(byte)
            if len(data) > 0:
                #print "Last: ",ord(data[len(data)-1])
                begin = time.time()
                total_data.append(data)
                #print "Response time: ",time.time()-begin
                #print ord(data[len(data)-2])
                if waitForBcc:
                    waitForBcc = False
                    #print "Got BCC!",data,name
                    break
                elif (ord(data[len(data)-1])==ord(ETX)) and (ord(data[len(data)-2]) != ord(ETX)):
                    #print "ETXEND! WAITING FOR BCC",name
                    #Received ETX but not BCC-byte. Set flag and wait for it and then break.
                    waitForBcc = True
                elif ord(data[len(data)-2])==ord(ETX):
                    #print "ETXEND!",name
                    break
                elif ord(data[len(data)-1])==ord('\n') and ord(data[len(data)-2])==ord('\r'):
                    #print "CRLFEND!",name
                    break
                elif ord(data[len(data)-1])==ord(ACK):
                    break
            #else:
                #print "NO DATA"
        except KeyboardInterrupt:
            break
            raise
        except Exception as e:
            #print e
            #raise
            pass
    #print "Out of loop",name
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
    
    #print "Returning data",name
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
        try:
            floatlist.append(float(s))
        except ValueError:
            print "ValueError when converting: ",s," to float."
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
    if size>599:
        print "Queue size is ",size," sending"
        doc_arr = []
        for i in range(0,size):
            doc = q.get()
            doc_arr.append(doc)
        dblocal.update(doc_arr)
        print ("%(db)s" % credentials),"-->",("%(protocol)s://%(user)s:%(passw)s@%(domain)s/%(db)s" % credentials)
        couchlocal.replicate("%(db)s" % credentials,"%(protocol)s://%(user)s:%(passw)s@%(domain)s/%(db)s" % credentials)
        q.task_done()

def send_to_db(doc, creds):
    url = ('%(protocol)s://%(domain)s/%(db)s' % creds)
    request = urllib2.Request(url, data=json.dumps(doc))
    auth = base64.encodestring('%(user)s:%(passw)s' % creds).replace("\n","")
    request.add_header('Authorization', 'Basic ' + auth)
    request.add_header('Content-Type', 'application/json')
    request.get_method = lambda: 'POST'
    urllib2.urlopen(request, timeout=1)    

i1 = 599
i2 = 599
data1_1 = None #192.168.1.3
data1_2 = None #192.168.1.4
def read_data(q,reply_q):
    global data1_1,data1_2,i1,i2
    #print "Running read_data"
    s = q.get()   
    # Send data
    t0 = time.time()
    name = s.getpeername()[0]
    print "Ethernet: ",name
    try:
        timeans = send(s,[SOH,"R1",STX,"100C00(1)",ETX])
        metertime =  ans_to_list_str(timeans)
        if name == "192.168.1.3":
            i1 = i1 + 1
        if name == "192.168.1.4":
            i2 = i2 + 1
        if i1 > 599 and name == "192.168.1.3":
            data1ans = send(s,[SOH,"R1",STX,"100800(1)",ETX])
            data1_1 =  ans_to_list(data1ans)
            i1 = 0
        if i2 > 599 and name == "192.168.1.4":
            data1ans = send(s,[SOH,"R1",STX,"100800(1)",ETX])
            data1_2 =  ans_to_list(data1ans)
            i2 = 0
        data1 = None
        if name == "192.168.1.3":
            data1 = data1_1
        elif name == "192.168.1.4":
            data1 = data1_2
        data2ans = send(s,[SOH,"R1",STX,"015200(1)",ETX])
        data2 = ans_to_list(data2ans)
        temp = send(s,[SOH,"R1",STX,"100700(1)",ETX])
        tempdata = ans_to_list(temp)
        #tempdata = [0.0]
        #print "Got answer from meter",name
        data = {
            "meter_time":metertime_to_time(metertime),
            "act_ener_imp": data1[0], #Wh
            "act_ener_exp": data1[1], #Wh
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
            "pha_volt_L1":data2[0], #V
            "pha_volt_L2":data2[1], #V
            "pha_volt_L3":data2[2], #V
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
            "pha_angle_L1":data2[15], #rad
            "pha_angle_L2":data2[16], #rad
            "pha_angle_L3":data2[17], #rad
            #"pow_fact_L1":data2[18], 
            #"pow_fact_L2":data2[19],
            #"pow_fact_L3":data2[20],
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
            "temperature":tempdata[0], #C
            "error":False
        }
        if name == "192.168.1.3":
            reply_q.put(["solar",data])
        elif name == "192.168.1.4":
            reply_q.put(["wind",data])
        #print "Putting reply",name
    except:
        data = {
            "meter_time":0,
            "act_ener_imp": 0, #Wh
            "act_ener_exp": 0, #Wh
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
            "act_ener_imp_L1": 0, #Wh
            "act_ener_imp_L2": 0, #Wh
            "act_ener_imp_L3": 0, #Wh
            "act_ener_exp_L1": 0, #Wh
            "act_ener_exp_L2": 0, #Wh
            "act_ener_exp_L3": 0, #Wh
            "pha_volt_L1":0, #V
            "pha_volt_L2":0, #V
            "pha_volt_L3":0, #V
            #"main_volt_L1_L2":0, #V
            #"main_volt_L2_L3":0, #V
            #"main_volt_L3_L1":0, #V
            "current_L1":0, #A
            "current_L2":0, #A
            "current_L3":0, #A
        #"pha_sym_volt_L1":data2[9], #rad
        #"pha_sym_volt_L2":data2[10], #rad
        #"pha_sym_volt_L3":data2[11], #rad
        #"pha_sym_current_L1":data2[12], #rad
        #"pha_sym_current_L2":data2[13], #rad
        #"pha_sym_current_L3":data2[14], #rad
            "pha_angle_L1":0, #rad
            "pha_angle_L2":0, #rad
            "pha_angle_L3":0, #rad
            #"pow_fact_L1":0, 
            #"pow_fact_L2":0,
            #"pow_fact_L3":0,
            "act_pow_L1":0, #W
            "act_pow_L2":0, #W
            "act_pow_L3":0, #W
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
            "tot_act_power":0, #W
        #"tot_rea_power":data2[37], #var
        #"tot_app_power":data2[38], #VA
            "tot_pow_fact":0,
        #"tot_pha_angle":data2[40],
            "frequency":0, #Hz
        #"vt_ratio":data2[42],
            "ct_ratio":0,
        #"sec_nom_volt":data2[44], #V
        #"sec_nom_cur":data2[45], #A
            "temperature":0, #C
            "error":True
        }
        if name == "192.168.1.3":
            reply_q.put(["solar",data])
        elif name == "192.168.1.4":
            reply_q.put(["wind",data])        
        #print "Power meter error"
    t1 = time.time()
    print "Ethernet: Done (",name,") ",(t1-t0)
    q.task_done()

def s16_to_int(s16):
    if s16 > 32767:
        return s16 - 65536
    else:
        return s16

def setRelay(relaynum,value):
    if relaynum<1 or relaynum > 2:
        print "Relay number must be 1 or 2."
        return
    ans = Pyro.write_coil(1+relaynum,value,unit=4)

def getRelay(relaynum):
    ans = Pyro.read_coils(1+relaynum,8,unit=4)
    return ans.bits[relaynum-1]

def read_modbus(q,reply_q):
    qaddr = q.get()
    data = {}
    t0 = time.time()
    for addr in qaddr:
        print "Modbus: ",addr
        if addr==1:
            try:
                ans = Pyro.read_input_registers(0, 56, unit=int(addr))
                data["dir"]=ans.registers[6]/100.0
                data["speed"]=ans.registers[5]/100.0
                data["temph"]=ans.registers[0]/100.0
                data["tempp"]=ans.registers[1]/100.0
                data["pressure"]=((ans.registers[3] << 16) + ans.registers[2])/100.0
                data["hum"]=(ans.registers[4])/100.0
                data["voltage"]=ans.registers[12]/100.0
                data["status"]=ans.registers[13]
                data["error"] = False
                reply_q.put([''.join(["anemo",str(addr)]),data])
                data = {}
            except (AttributeError,OSError):
                data["dir"]=0
                data["speed"]=0
                data["temph"]=0
                data["tempp"]=0
                data["pressure"]=0
                data["hum"]=0
                data["voltage"]=0
                data["status"]=0
                data["error"] = True
                reply_q.put([''.join(["anemo",str(addr)]),data])
                data = {}
                print "Error reading anemometer ",addr
                pass
        elif addr==2:
            try:
                ans = Pyro.read_input_registers(0, 56, unit=int(addr))
                data["dir"]=ans.registers[6]/100.0
                data["speed"]=ans.registers[5]/100.0
                data["temph"]=ans.registers[0]/100.0
                data["hum"]=(ans.registers[4])/100.0
                data["voltage"]=ans.registers[12]/100.0
                data["status"]=ans.registers[13]
                data["error"] = False
                reply_q.put([''.join(["anemo",str(addr)]),data])
                data = {}
            except (AttributeError,OSError):
                data["dir"]=0
                data["speed"]=0
                data["temph"]=0
                data["hum"]=0
                data["voltage"]=0
                data["status"]=0
                data["error"] = True
                reply_q.put([''.join(["anemo",str(addr)]),data])
                data = {}
                print "Error reading anemometer ",addr
                pass
        elif addr==3:
            try:    
                ans = Pyro.read_input_registers(0, 10, unit=int(addr))
                data["status"] = ans.registers[3]
                if ans.registers[0] == 8:
                    ans2 = Pyro.read_input_registers(26,1,unit=3)
                    data["error_code"] = ans2.registers[0]
                data["radiance"] = s16_to_int(ans.registers[5])/1.0
                data["raw_radiance"] = s16_to_int(ans.registers[6])
                data["temp"] = s16_to_int(ans.registers[8])/10.0
                data["ext_voltage"] = s16_to_int(ans.registers[9])/10.0
                data["error"] = False
                reply_q.put(["pyro",data])
                data = {}
            except (AttributeError,OSError):
                data["status"] = 0
                data["radiance"] = 0
                data["raw_radiance"] = 0
                data["temp"] = 0
                data["ext_voltage"] = 0
                data["error"] = True
                reply_q.put(["pyro",data])
                data = {}
                print "Pyranometer data AttributeError. Error in reading Pyranometer, incomplete data."
                pass
        elif addr==4:
            try:
                ans = Pyro.read_input_registers(0, 2, unit=int(addr))
                data["dir"]=ans.registers[1]/1.0
                data["speed"]=ans.registers[0]/10.0
                print "DIR SPEED",data["dir"],data["speed"]
                data["error"] = False
                reply_q.put([''.join(["anemo",str(addr)]),data])
                data = {}
                if getRelay(1) == 0: #Activate relay on startup
                    setRelay(1,1)
                if int(time.time()%86400) < 2 and int(time.time()%86400) > 0: #Turn relay off once each midnight to restart anemometer
                    setRelay(1,0)
                    time.sleep(1)
                    setRelay(1,1)
            except (AttributeError,OSError):
                data["dir"]=0
                data["speed"]=0
                data["error"] = True
                reply_q.put([''.join(["anemo",str(addr)]),data])
                data = {}
                print "Error reading anemometer ",addr
                pass
            finally:
                t1 = time.time()
                print "Modbus: Done. ",(t1-t0)
                q.task_done()

def read_modbus_pyro(q,reply_q):
    reg = q.get()
    data = {}

def main():
    passw = ""
    user = ""
    url = ""

    #There is got to be a text file named ".credentials" in the same folder as the
    #python script, containg: <user>,<passw>,<domain>,<repldb_name>,<dbname>
    #example: user1,password1,domain,database-repl,database
    try:
        with open('.credentials_remote', 'r') as f:
            file_data = f.read()
            #print read_data
            creds = file_data.split(',')
            user = creds[0]
            passw = creds[1]
            protocol = creds[2]
            domain = creds[3]
            dbname = creds[4].replace('\n','')
        with open('.credentials_local', 'r') as f:
            file_data = f.read()
            #print read_data
            creds = file_data.split(',')
            luser = creds[0]
            lpassw = creds[1]
            lprotocol = creds[2]
            ldomain = creds[3]
            ldbname = creds[4].replace('\n','')
    except:
        print "Error opening credentials file."
        raise

    credentials_remote = {
      'user': user,
      'passw': passw,
      'protocol':protocol,
      'domain': domain,
      'db': dbname
    }
    credentials_local = {
      'user': luser,
      'passw': lpassw,
      'protocol': lprotocol,
      'domain': ldomain,
      'db': ldbname
    }

    print "Local creds: ",credentials_local
    print "Remote creds: ",credentials_remote
    #print credentials
    while not setup_couchdb_local(credentials_local):
        print "Could not connect to database. Retrying soon..."
        time.sleep(10)
        

    addr_q = Queue.Queue()
    reply_q = Queue.Queue()
    send_q = Queue.Queue()
    modbus_addr_q = Queue.Queue()    
    

    socketlist = setup_socket("192.168.1.3")
    s1 = socketlist[0]
    while True:
        try:
            print "Connecting to 192.168.1.3"
            connect(s1,socketlist[1])
            break
        except:
            print "Could not connect to 192.168.1.3"
            time.sleep(10)
            pass

    socketlist = setup_socket("192.168.1.4")
    s2 = socketlist[0]
    while True:
        try:
            print "Connecting to 192.168.1.4"
            connect(s2,socketlist[1])
            break
        except:
            print "Could not connect to 192.168.1.4"
            time.sleep(10)
            pass

    print "Initiating connection with 192.168.1.3 and 192.168.1.4"

    while True:
        try:
            ceweserial = send(s1,'/?!\r\n')
            if ceweserial == "/CWI5CW011163\r":
                print "Connection established with ",ceweserial
                send(s1,[ACK,"051\r\n"]) #050 Data readout,#051 programming mode
                send(s1,[SOH,"P2",STX,"(ABCDEF)",ETX]) #<SOH>P2<STX>(ABCDEF)<ETX><BCC>
                break
            else:
                time.sleep(10)
        except:
            time.sleep(10)
            pass

    while True:
        try:
            ceweserial = send(s2,'/?!\r\n')
            if ceweserial == "/CWI5CW011162\r":
                print "Connection established with ",ceweserial
                send(s2,[ACK,"051\r\n"]) #050 Data readout,#051 programming mode
                send(s2,[SOH,"P2",STX,"(ABCDEF)",ETX]) #<SOH>P2<STX>(ABCDEF)<ETX><BCC>
                break
            else:
                time.sleep(10)
        except:
            time.sleep(10)
            pass


    times = []



    try:
        while True:
            t0 = time.time()
            thread1 = threading.Thread(target=read_data,args=(addr_q,reply_q,))
            thread2 = threading.Thread(target=read_data,args=(addr_q,reply_q,))
            thread3 = threading.Thread(target=send_to_db2,args=(send_q,credentials_remote,))
            thread4 = threading.Thread(target=read_modbus,args=(modbus_addr_q,reply_q,))

            thread1.daemon = True
            thread2.daemon = True
            thread3.daemon = True
            thread4.daemon = True


            addr_q.put(s1)
            addr_q.put(s2)
            modbus_addr_q.put([1,2,3,4])

            thread1.start()
            thread2.start()
            thread3.start()
            thread4.start()

            #print "Threads running"
            addr_q.join()
            modbus_addr_q.join()
            #print "Reply queue size: ", reply_q.qsize()
            ansarr = []
            #print "Threads joined"            
            ansarr.append(reply_q.get(block=True))
            #print "Read first",ansarr[0]
            ansarr.append(reply_q.get(block=True))
            #print "Read second",ansarr[1]
            ansarr.append(reply_q.get(block=True))
            #print "Read third",ansarr[2]
            ansarr.append(reply_q.get(block=True))
            #print "Read fourth",ansarr[3]
            ansarr.append(reply_q.get(block=True))
            #print "Read fifth",ansarr[4]
            #print "Reading reply_q"
            for post in ansarr:
                #print "POST: ",post[0]
                if post[0] == "wind":
                    wind = post[1]
                elif post[0] == "solar":
                    solar = post[1]
                elif post[0] == "pyro":
                    pyro = post[1]
                elif post[0] == "anemo1":
                    anemo1 = post[1]
                elif post[0] == "anemo2":
                    anemo2 = post[1]
                elif post[0] == "anemo4":
                    anemo4 = post[1]
                
            try:
                data = {
                    "wind":wind,
                    "solar":solar,
                    "pyro":pyro,
                    "anemo1":anemo1,
                    "anemo2":anemo2,
                    "anemo4":anemo4,
                    "timestamp":int(time.time()*1000)
                }

                print "Writing to file..."
                sampleToFile(json.dumps(data))
                print "File done. Now storing in ram."
                #print data
                send_q.put(data)
                print "Done."
                t1 = time.time()
                total = t1-t0
                #if (1-total)>0.05:
                #    time.sleep(1-total)
                now = time.time()
                #times.append(now-t0)
                print ".",total,' ',now
            except UnboundLocalError:
                pass
            #send_to_db2(data)
            #send('END') 
    finally:
        send_without_recv(s1,[SOH,"B0",ETX])
        send_without_recv(s2,[SOH,"B0",ETX])
        s1.close()
        s2.close()
        Pyro.close()
        print "Closed."
        sum = 0
        for i in times:
            sum+=i
        if len(times)>0:
            print "Avg: ",sum/len(times)
            #return
            #print >>sys.stderr, 'closing socket'
            #s.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise
    #while True:
    #    try:
    #        main()
    #    except:
    #        print "Error, retrying in 10 seconds"
    #        time.sleep(10)
    #        pass
