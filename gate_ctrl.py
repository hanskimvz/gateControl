import os, time, sys
import socket
import struct
import threading
import json, base64
import pymysql
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth


with open ("setting.json") as f:
    SETTING = json.loads(f.read())

# print (SETTING)

if not SETTING :
    print ("setting file error")
    sys.exit()

if not SETTING.get('device_ip'):
    print ("setting, device_ip error")
    sys.exit()

if not SETTING.get('device_port'):
    SETTING['device_port'] = 7101

if not SETTING.get('address'):
    SETTING['address'] = 1

if not SETTING.get('query_interval'):
    SETTING['query_interval'] = 100
# print (SETTING)
Running = True

TZ_OFFSET =  3600*9

# MODEL = "ZC10RMO12-44S1" # DC12V 4channel RS485 Modbus RTU
"""
1       address 1Byte
2       function 1byte      01: read relay sts, 02: read sensor, 05: out relay, 06:trigger relay, 
3,4     register address
5,6     register data
7,8     CRC16

"""

relaySts = [0,0,0,0]
sensorSts = [0,0,0,0]

def modbusCrc(msg:str) -> int:
    crc = 0xFFFF
    for n in range(len(msg)):
        crc ^= msg[n]
        for i in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

def retrieveData(data):
    res = b''
    data = data.replace(' ','')
    for i in range(0, len(data),2):
        d = data[i:i+2]
        x = struct.pack("B", int(d,16))
        res += x
    return  res


def dataRelayOut(addr, ch, flag):
    data  = struct.pack("B", addr)
    data += struct.pack("B", 0x05)
    data += struct.pack("B", ch>>8&0xFF)
    data += struct.pack("B", ch&0xFF)
    if flag:
        data += struct.pack("B", 0xFF)
    else :
        data += struct.pack("B", 0x00)
    data += struct.pack("B", 0x00)

    crc = modbusCrc(data)
    data += struct.pack("B",crc&0xFF)
    data += struct.pack("B",crc>>8&0xFF)
    return data

def dataRelayTrigger(addr, ch, msecs):
    msecs //= 100
    data  = struct.pack("B", addr)
    data += struct.pack("B", 0x06)
    data += struct.pack("B", 0x78)
    data += struct.pack("B", ch&0xFF)
    data += struct.pack("B", (msecs>>8)&0xFF)
    data += struct.pack("B", msecs&0xFF)

    crc = modbusCrc(data)
    data += struct.pack("B",crc&0xFF)
    data += struct.pack("B",crc>>8&0xFF)
    return data

def dataRelayToggle(addr, ch):
    data  = struct.pack("B", addr)
    data += struct.pack("B", 0x05)
    data += struct.pack("B", 0x00)
    data += struct.pack("B", ch&0xFF)
    data += struct.pack("B", 0x55)
    data += struct.pack("B", 0x00)

    crc = modbusCrc(data)
    data += struct.pack("B",crc&0xFF)
    data += struct.pack("B",crc>>8&0xFF)
    return data

def dataRelaySts(addr, ch):
    data  = struct.pack("B", addr)
    data += struct.pack("B", 0x01)
    data += struct.pack("B", ch>>8&0xFF)
    data += struct.pack("B", ch&0xFF)
    data += struct.pack("B", 0x00)
    data += struct.pack("B", 0x01)

    crc = modbusCrc(data)
    data += struct.pack("B",crc&0xFF)
    data += struct.pack("B",crc>>8&0xFF)
    return data    


def dataSensorSts(addr):
    data  = struct.pack("B", addr)
    data += struct.pack("B", 0x02)
    data += struct.pack("B", 0x00)
    data += struct.pack("B", 0x00)
    data += struct.pack("B", 0x00)
    data += struct.pack("B", 0x04)

    crc = modbusCrc(data)
    data += struct.pack("B",crc&0xFF)
    data += struct.pack("B",crc>>8&0xFF)
    return data   



def checkData(dd):
    for d in dd:
        print ("%02X" %d, end=" ")
    print ()


def getSensorData(s):
    s.send(dataSensorSts(SETTING['address']))
    d = s.recv(1024)
    arr = []
    print (s)
    print (len(d), end=" ")
    if len(d) <6:
        # s.close()
        time.sleep(2)
        return False
    for i in range(4):
        x = (d[3]>>i) &1
        arr.append(x)

    return arr



def putRelayTriggerSingle(ch, msecs):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # print(s)
    try:
        s.connect((SETTING['device_ip'], int(SETTING['device_port'])))
    except Exception as e:
        print (e)
        s.close()
        return False
    
    x = s.send(dataRelayTrigger(SETTING['address'], ch, msecs))
    # print(x)
    # time.sleep(1)
    # d = s.recv(1024)
    # checkData(d)
    s.close()
    return True

def getSensorsSingle():
    global sensorSts
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(s)
    try:
        s.connect((SETTING['device_ip'], int(SETTING['device_port'])))
    except Exception as e:
        print (e)
        s.close()
        return False
    
    x = s.send(dataSensorSts(SETTING['address']))
    print(x)
    d = s.recv(1024)
    checkData(d)
    for p in range(4):
        sensorSts[p] = (d[3]>>p) &1
    
    print (sensorSts)
    s.close()


def getSnapshot(device_ip=None, port=80, userid='root', userpw='pass', format='b64'):

    cgi_str = "nvc-cgi/operator/snapshot.fcgi"
    url = 'http://%s:%d/%s' %(device_ip, port, cgi_str)
    # cgi_str = arr_cgi_str["snapshot"][device_family]

    try:
        r= requests.get(url , auth=HTTPBasicAuth(userid, userpw))
    except Exception as e:
        print (url + "," + str(e))
        return False
    
    if format == 'b64':
        data = b'data:image/jpg;base64,' + base64.b64encode(r.content)
        data = data.decode('utf-8')
    return data
    



def dbconMaster(host = '', user = '', password = '', db = '', charset ='', port=0): #Mysql
    try:
        dbcon = pymysql.connect(host=host, user=str(user), password=str(password),  charset=charset, port=int(port))
    except pymysql.err.OperationalError as e :
        print (str(e))
        return None

    return dbcon

# dbcon = dbconMaster(SETTING['MYSQL']['host'],SETTING['MYSQL']['user'],SETTING['MYSQL']['pass'], SETTING['MYSQL']['db_name'], SETTING['MYSQL']['charset'])
# with dbcon:
#     cur = dbcon.cursor()
#     sq = "select pk, timestamp, eventinfo from %s.%s where flag='n' order by timestamp desc " %(SETTING['MYSQL']['db_name'], SETTING['MYSQL']['table'])
#     print (sq)
#     cur.execute(sq)
#     rows = cur.fetchall()
#     for row in rows:
#         print (row)
#         print (int(time.time()) - int(row[1]))
#         if time.time() + TZ_OFFSET - int(row[1]) <10:
#             putRelayTriggerSingle(0,1000)
#         sq = "update %s.%s set flag='y' where pk=%d" %(SETTING['MYSQL']['db_name'], SETTING['MYSQL']['table'], int(row[0]))
#         print (sq)
#         cur.execute(sq)
#     dbcon.commit()



class thMainTimer():
    def __init__(self, t=1):
        self.name = "gate_control"
        self.t = t
        self.last = 0
        self.i = 0
        self.thread = threading.Timer(1, self.handle_function)
        self.idle = 3600

    def handle_function(self):
        self.main_function()
        self.last = int(time.time())
        self.thread = threading.Timer(self.t, self.handle_function)
        self.thread.start()
    
    def main_function(self):
        ts = time.time()
        str_s = "======== Gate control, starting %d ========" %self.i
        print(str_s)
        dbcon = dbconMaster(SETTING['MYSQL']['host'],SETTING['MYSQL']['user'],SETTING['MYSQL']['pass'], SETTING['MYSQL']['db_name'], SETTING['MYSQL']['charset'])
        with dbcon:
            cur = dbcon.cursor()
            sq = "select pk, timestamp, eventinfo from %s.%s where flag='n' order by timestamp desc " %(SETTING['MYSQL']['db_name'], SETTING['MYSQL']['table'])
            print (sq)
            cur.execute(sq)
            rows = cur.fetchall()
            for row in rows:
                print (row)
                print (int(time.time()) - int(row[1]))
                if time.time() + TZ_OFFSET - int(row[1]) <10:
                    putRelayTriggerSingle(0,1000)
                    snapshot = getSnapshot(device_ip=SETTING['device_ip'], port=80, userid='root', userpw='pass',  format='b64')
                    sq = "update %s.%s set snapshot='%s' where pk=%d" %(SETTING['MYSQL']['db_name'], SETTING['MYSQL']['table'], snapshot, int(row[0]))
                    cur.execute(sq)

                sq = "update %s.%s set flag='y' where pk=%d" %(SETTING['MYSQL']['db_name'], SETTING['MYSQL']['table'], int(row[0]))
                print (sq)
                cur.execute(sq)
            dbcon.commit()


        self.i += 1

    def start(self):
        str_s = "starting Gate Control Service"
        print(str_s)
        self.last = int(time.time())
        self.thread.start()

    # def is_alive(self):
    #     global watchDogTsActiveCounting
    #     if int(time.time()) - self.last  > 600:
    #         if int(time.time()) - watchDogTsActiveCounting > 600:
    #             print ("not alive %d" %watchDogTsActiveCounting)
    #             return False
    #     return True
    
    def cancel(self):
        str_s = "stopping Gate control Servce"
        print(str_s)
        self.thread.cancel()
    
    def stop(self):
        self.cancel()

if __name__ == '__main__':
    tc = thMainTimer()
    tc.start()
    while Running:
        time.sleep(1)

sys.exit()

class thMain(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self, name='getSensors')
        self.daemon = True
        self.running = True
        self.i = 0
       
    def run(self):
        global Running
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as  msg:
            print("Could not create socket. Error Code: {0}, Error: {1}".format(str(msg[0], msg[1])))
            return False
        
        print ("[-] Socket Created")
        xp = self.s.connect((SETTING['device_ip'], int(SETTING['device_port'])))
        print(xp)
        if xp:
            Running = False
        print ("connected")

        while self.running:

            try:
                x = self.s.send(dataSensorSts(SETTING['address']))
                d = self.s.recv(1024)

            except Exception as e:
                print (e)
                if str(e).find("Broken pipe") >0:
                    self.s.close()
                    self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.s.connect((SETTING['device_ip'], int(SETTING['device_port'])))
                    print ("reconnected")

                time.sleep(0.5)
                continue
            if len(d) <6:
                print ("length must be 6")
                # self.s.close()
                # time.sleep(1)
                # self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # self.s.connect((SETTING['device_ip'], int(SETTING['device_port'])))
                # print ("reconnected")
                continue
            if not int(d[0]) == int(SETTING['address']):
                print ("data d0 error")
                continue
            if not int(d[1]) == 2:
                print(d)
                print ("data d1 error, read 2")
                continue
            
            for p in range(4):
                sensorSts[p] = (d[3]>>p) &1

            if sensorSts[0] == 1:
              self.s.send(dataRelayTrigger(SETTING['address'], 0, 700)) 
              time.sleep(1)

            # self.s.send(dataRelayTrigger(SETTING['address'], 1, 70))  
            # self.s.send(dataRelayOut(SETTING['address'], 0, 1))
            # time.sleep(SETTING['query_interval'] // 1000)
            # self.s.send(dataRelayOut(SETTING['address'], 0, 0))

            # if not sensorSts:
            #     time.sleep(1)
            #     continue
            # try:
            #     sensorSts = getSensorData(self.s)
            
            # except:
            #     self.s.connect((SETTING['device_ip'], int(SETTING['device_port'])))
            #     print ("reconnected")

            print (self.i, sensorSts)
            time.sleep(SETTING['query_interval'] / 1000)
            self.i +=1

            if self.i > 100:
                self.running = False
                Running = False


        self.s.close()

    def stop(self):
        self.running = False


# if __name__ == '__main__':
#     for i in range(10):
#         putRelayTriggerSingle(0,1000)
#         with open ("out") as f:
#             f.write()
#         # getSensorsSingle()
#         time.sleep(0.3)
    # th_s = thMain()
    # th_s.start()

    # while Running:
    #     time.sleep(1)

# cl_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# cl_s.connect((ip, port))
# print ("connected")

# dd = dataRelayOut(1,1,0)
# dd = dataSensorSts(1)
# checkData(dd)
# cl_s.send(dd)
# for i in range (100):
#     x = getSensorData(cl_s)
#     print (x)
#     putRelayTrigger(cl_s, 0, 1000)
#     time.sleep(2)


# # checkData(d)

# print (cl_s)

# cl_s.close()

# print(cl_s)