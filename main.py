import os, sys, time
import json, base64
import cv2 as cv
import numpy as np
import socket
import requests
import threading
from ocr import get_plate_chars
import pymysql


configVars = []
with open("setting.json", "r", encoding="utf8") as f:
    configVars = json.loads(f.read())

CAMERA = configVars['CAMERAS']
MYSQL = configVars['MYSQL']
SERVER = configVars['SERVER']




def dbconMaster(host = '', user = '', password = '', db = '', charset ='', port=0): #Mysql
	if not host :
		host = MYSQL['host']
	if not user:
		user = MYSQL['user']
	if not password :
		password = MYSQL['pass']
	if not db:
		db = MYSQL['db_name']
	if not charset:
		charset = MYSQL['charset']
	if not port:
		port = MYSQL['port']


	try:
		dbcon = pymysql.connect(host=host, user=str(user), password=str(password),  charset=charset, port=int(port))
	# except pymysql.err.OperationalError as e :
	except Exception as e :
		print ('dbconerr', str(e))
		return None
	
	return dbcon


# import numpy as np
# import cv2 as cv

# pk =15251

# dbCon = dbconMaster()
# with dbCon:
#     cur =dbCon.cursor()
#     # sq = "select pk, snapshot from " + MYSQL['db_name'] + "."+ MYSQL['log_table'] +" where id != '' order by timestamp desc limit 6,2"
#     # sq = "select pk, snapshot, timestamp from " + MYSQL['db_name'] + ".event_post where IP_addr= '192.168.3.19' order by timestamp desc limit 650,2"
#     sq = "select pk, snapshot, timestamp from " + MYSQL['db_name'] + ".event_post where pk=%d " %pk
#     print (sq)
#     cur.execute(sq)
#     rows = cur.fetchall()
#     for row in rows:
#         # print (row[1])
#         info, imgb64 = row[1].split(b"base64,")
#         img = base64.b64decode(imgb64.decode())
#         image_nparray = np.asarray(bytearray(img), dtype=np.uint8)
#         img_ori = cv.imdecode(image_nparray, cv.IMREAD_COLOR)		
        
#         x0,y0,x1,y1 = 500,200,1400,700
#         img = img_ori[y0:y1,x0:x1]
#         cv.imwrite("res%d.jpg" %(int(row[0])), img)
#         print (row[0], row[2], end = "")
#         rs = get_plate_chars(img)
#         print (rs)
		

def openDoor():
	for cam in CAMERA:
		if cam['fordoor']=='y':
			url ="http://%s:%s@%s/%s1" %(cam['userid'], cam['userpw'], cam['address'], cam['DO_cgi']['trig'])
			print ("door open", url)
			requests.get(url)
            
	
# openDoor()

def getPlatesDB():
    arr_plate = list()
    dbCon = dbconMaster()
    with dbCon:
        cur =dbCon.cursor()
        sq = "select id, plate from " + MYSQL['db_name'] + "."+MYSQL['user_table']
        print (sq)
        cur.execute(sq)
        rows = cur.fetchall()
        for row in rows:
            if row[1]:
                arr_plate.append((row[0], row[1][-4:]))
    return arr_plate

def findSimilarity(arr_db_plate,rec_number):
    for id, plate in arr_db_plate:
        if rec_number.find(plate)>=0:
            return id
		

    return False

def logDB(userid, eventinfo, snapshot):
    timestamp = round(time.time() + 3600*9,3)
    regdate =time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(timestamp)))
    dbCon = dbconMaster()
    with dbCon:
        cur =dbCon.cursor()
        sq = "select pk,timestamp from " + MYSQL['db_name'] + "."+MYSQL['log_table'] + " where timestamp < %.3f order by timestamp asc limit 1" %(timestamp-2592000)
        # sq = "select pk from " + MYSQL['db_name'] + "."+MYSQL['log_table'] + " where timestamp > %.3f order by timestamp asc limit 1" %(timestamp)
        print (sq)
        cur.execute(sq)
        if cur.rowcount:
            pk = int(cur.fetchone()[0])
            sq = "update " + MYSQL['db_name']+"."+ MYSQL['log_table'] + " set  regdate='%s', timestamp=%.3f, id='%s', eventinfo='%s', user_agent='LPR', snapshot='%s', flag='n'  where pk=%d" %(regdate, timestamp, userid, eventinfo, snapshot, pk)
            
        else:
            sq = "insert into " + MYSQL['db_name'] + "." + MYSQL['log_table'] + "(regdate, timestamp, id, eventinfo, user_agent, snapshot, flag)  values('%s', %.3f, '%s', '%s',  'LPR', '%s', 'n')" %(regdate, timestamp, userid, eventinfo , snapshot)

        print (sq)


def getSnapshots():
    arr_snapshot = list()
    for cam in CAMERA:
        # print (cam)
        if cam['forlpr'] == 'y':
            
            url ="http://%s:%s@%s%s" %(cam['userid'],cam['userpw'], cam['address'], cam['snapshot_cgi'])
            # print (url)
            for i in range(2):
                arr_snapshot.append((requests.get(url).content, cam['window']))
                time.sleep(0.2)
    return arr_snapshot
        

# rs = findSimilarity(arr_plate, '9680')
# print (rs)
# logDB('hanskim','ee','snaps')
def proc_lpr():

    snapshots =  getSnapshots()
    for i, (snapshot, window) in enumerate(snapshots):
        image_nparray = np.asarray(bytearray(snapshot), dtype=np.uint8)
        img_ori = cv.imdecode(image_nparray, cv.IMREAD_COLOR)
        x0,y0,x1,y1 = window	
        img = img_ori[y0:y1,x0:x1]
        cv.imwrite("res%d.jpg" %i, img)
        etime, plates =  get_plate_chars(img)
        for plate in plates:
            print (plate)
            userid = findSimilarity(arr_plate, plate)
            print ("userid", userid)
            if (userid):
                openDoor()
                imgb64 = b'data:image/jpg;base64,' + base64.b64encode(snapshot)
                imgb64 =  imgb64.decode('ascii')                
                logDB(userid, json.dump(plates), imgb64)
                break

def recv_timeout(conn,timeout=2): 
    # TLSS only since 2022.03.20
    conn.setblocking(0)
    total_data=[]
    data=''
    begin=time.time()
    while 1:
        if total_data and time.time()-begin > timeout:
            break
        elif time.time()-begin > timeout*2:
            break
            
        try:
            data = conn.recv(1024)
            if data:
                total_data.append(data)
                begin=time.time()
            else:
                time.sleep(0.1)
        except:
            pass
    return  b''.join(total_data)


class  ThLprProc(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.Running = True
        self.daemon= True
    
    def run(self):
        print ("stating gate control")
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as  msg:
            print("Could not create socket. Error Code: {0}, Error: {1}".format(str(msg[0], msg[1])))
            sys.exit(0)
        print("[-] Socket Created(COUNT_EVENT)")

        try:
            self.s.bind((SERVER['host'], int(SERVER['port'])))
            print("[-] Socket Bound to port {0}".format(str(SERVER['port'])))
        
        except socket.error as msg:
            print("EventCounting, Bind Failed. Error: {0}".format(str(msg)))
            self.s.close()
            sys.exit()

        self.s.listen(30) 
        print("gate Control Engine: Listening...") 

        while self.Running :
            self.conn, self.addr = self.s.accept()
            print ("EVENT PUSH: %s:%s connected" %(self.addr[0], str(self.addr[1])))
            data= recv_timeout(self.conn)
            self.conn.close()
            print (data)
            if data.find(b"/lpr") >0:
                self.t0 = threading.Thread(target=proc_lpr, args=( ))
                self.t0.start()

        self.s.close()
        print ("stopping Event Counting")
    
    def stop(self):
        self.Running = False

if __name__ == "__main__":
    arr_plate =   getPlatesDB()       
    # proc_lpr()

    te = ThLprProc()
    te.start()
    # for i in range(100):
    while True:
        # print (i, te, te.is_alive())
        if not te.is_alive():
            te = ThLprProc()
            te.start()
        time.sleep(60)
    te.stop()