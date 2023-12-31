import os, time, sys
import socket
import struct

ip = "192.168.3.19"
port = 7101
data = b'\x01\x06\x78\x00\x00\x07\xD0\xA8'
data = '01020000000479C9'
data = '010678000007D0A8'


def retrievedata(data):
    res = b''
    for i in range(0, len(data),2):
        d = data[i:i+2]
        x = struct.pack("B", int(d,16))
        res += x
    return  res

dd = retrievedata(data)



cl_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
cl_s.connect((ip,port))
print ("connected")
cl_s.send(dd)

d = cl_s.recv(1024)

print (d)

cl_s.close()