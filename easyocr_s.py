import time, sys, os
import easyocr
import cv2

THRESHOLD = 0.5

reader = easyocr.Reader(['ko', 'en'])

def read(img_path):
    img = cv2.imread(img_path)

    result = reader.readtext(img_path)

    r = []

    for bbox, text, conf in result:
        if conf > THRESHOLD:
            r.append(text)
            cv2.rectangle(img, pt1=(int(bbox[0][0]), int(bbox[0][1])), pt2=(int(bbox[2][0]), int(bbox[2][1])), color=(0, 255, 0), thickness=3)

    print(r)
    cv2.imwrite("res.jpg", img)

fname = "car.jpg"
read(fname)