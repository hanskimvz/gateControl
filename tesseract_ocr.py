import os, time, sys
from PIL import Image
import pytesseract
import cv2 as cv
import numpy as np

pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

def get_plate_chars(img):
    ts = time.time()
    MIN_AREA = 60
    MIN_WIDTH, MIN_HEIGHT = 2, 8
    MIN_RATIO, MAX_RATIO = 0.2, 1.0  #w/h

    height, width, channel = img.shape

    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    img_blurred = cv.GaussianBlur(gray, ksize=(5, 5), sigmaX=0)
    img_blur_thresh = cv.adaptiveThreshold(
        img_blurred,
        maxValue=255.0,
        adaptiveMethod=cv.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv.THRESH_BINARY_INV,
        blockSize=9, #19
        C=5
    )

    img_thresh = cv.adaptiveThreshold(
        gray,
        maxValue=255.0,
        adaptiveMethod=cv.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv.THRESH_BINARY_INV,
        blockSize=19,
        C=9
    )
    contours, _ = cv.findContours(
        # img_blur_thresh,
        img_thresh,
        mode=cv.RETR_LIST,
        method=cv.CHAIN_APPROX_SIMPLE
    )

    contours_dict = []
    for contour in contours:
        x, y, w, h = cv.boundingRect(contour)
        contours_dict.append({'contour': contour, 'x': x, 'y': y, 'w': w,'h': h, 'cx': x + (w / 2),'cy': y + (h / 2) })

    possible_contours = []
    cnt = 0
    for d in contours_dict:
        area = d['w'] * d['h']
        ratio = d['w'] / d['h']

        if area > MIN_AREA and d['w'] > MIN_WIDTH and d['h'] > MIN_HEIGHT and MIN_RATIO < ratio < MAX_RATIO:
            d['idx'] = cnt
            cnt += 1
            possible_contours.append(d)

    def find_chars(contour_list):
        MAX_DIAG_MULTIPLYER = 5
        MAX_ANGLE_DIFF = 12.0
        MAX_AREA_DIFF = 0.5
        MAX_WIDTH_DIFF = 0.8
        MAX_HEIGHT_DIFF = 0.2
        MIN_N_MATCHED = 3

        matched_result_idx = []

        for d1 in contour_list:
            matched_contours_idx = []
            for d2 in contour_list:
                if d1['idx'] == d2['idx']:
                    continue

                dx = abs(d1['cx'] - d2['cx'])
                dy = abs(d1['cy'] - d2['cy'])

                diagonal_length1 = np.sqrt(d1['w'] ** 2 + d1['h'] ** 2)

                distance = np.linalg.norm(np.array([d1['cx'], d1['cy']]) - np.array([d2['cx'], d2['cy']]))
                if dx == 0:
                    angle_diff = 90
                else:
                    angle_diff = np.degrees(np.arctan(dy / dx))
                area_diff = abs(d1['w'] * d1['h'] - d2['w'] * d2['h']) / (d1['w'] * d1['h'])
                width_diff = abs(d1['w'] - d2['w']) / d1['w']
                height_diff = abs(d1['h'] - d2['h']) / d1['h']

                if distance < diagonal_length1 * MAX_DIAG_MULTIPLYER \
                        and angle_diff < MAX_ANGLE_DIFF and area_diff < MAX_AREA_DIFF \
                        and width_diff < MAX_WIDTH_DIFF and height_diff < MAX_HEIGHT_DIFF:
                    matched_contours_idx.append(d2['idx'])

            matched_contours_idx.append(d1['idx'])

            if len(matched_contours_idx) < MIN_N_MATCHED:
                continue

            matched_result_idx.append(matched_contours_idx)

            unmatched_contour_idx = []
            for d4 in contour_list:
                if d4['idx'] not in matched_contours_idx:
                    unmatched_contour_idx.append(d4['idx'])

            unmatched_contour = np.take(possible_contours, unmatched_contour_idx)

            recursive_contour_list = find_chars(unmatched_contour)

            for idx in recursive_contour_list:
                matched_result_idx.append(idx)

            break

        return matched_result_idx

    result_idx = find_chars(possible_contours)
    matched_result = []
    for idx_list in result_idx:
        matched_result.append(np.take(possible_contours, idx_list))

    PLATE_WIDTH_PADDING = 1.3  # 1.3
    PLATE_HEIGHT_PADDING = 1.5  # 1.5
    MIN_PLATE_RATIO = 3
    MAX_PLATE_RATIO = 10

    plate_imgs = []
    for i, matched_chars in enumerate(matched_result):
        sorted_chars = sorted(matched_chars, key=lambda x: x['cx'])

        plate_cx = (sorted_chars[0]['cx'] + sorted_chars[-1]['cx']) / 2
        plate_cy = (sorted_chars[0]['cy'] + sorted_chars[-1]['cy']) / 2

        plate_width = (sorted_chars[-1]['x'] + sorted_chars[-1]['w'] - sorted_chars[0]['x']) * PLATE_WIDTH_PADDING

        sum_height = 0
        for d in sorted_chars:
            sum_height += d['h']

        plate_height = int(sum_height / len(sorted_chars) * PLATE_HEIGHT_PADDING)

        triangle_height = sorted_chars[-1]['cy'] - sorted_chars[0]['cy']
        triangle_hypotenus = np.linalg.norm(
            np.array([sorted_chars[0]['cx'], sorted_chars[0]['cy']]) -
            np.array([sorted_chars[-1]['cx'], sorted_chars[-1]['cy']])
        )

        angle = np.degrees(np.arcsin(triangle_height / triangle_hypotenus))
        rotation_matrix = cv.getRotationMatrix2D(center=(plate_cx, plate_cy), angle=angle, scale=1.0)
        img_rotated = cv.warpAffine(img_thresh, M=rotation_matrix, dsize=(width, height))
        img_cropped = cv.getRectSubPix(img_rotated, patchSize=(int(plate_width), int(plate_height)), center=(int(plate_cx), int(plate_cy)))

        if img_cropped.shape[1] / img_cropped.shape[0] < MIN_PLATE_RATIO or img_cropped.shape[1] / img_cropped.shape[0] < MIN_PLATE_RATIO > MAX_PLATE_RATIO:
            continue

        plate_imgs.append(img_cropped)

    plate_chars = set()
    for i, plate_img in enumerate(plate_imgs):
        plate_img = cv.resize(plate_img, dsize=(0, 0), fx=1.6, fy=1.6)
        _, plate_img = cv.threshold(plate_img, thresh=0.0, maxval=255.0, type=cv.THRESH_BINARY | cv.THRESH_OTSU)
        
        contours, _ = cv.findContours(plate_img, mode=cv.RETR_LIST, method=cv.CHAIN_APPROX_SIMPLE)
        plate_min_x, plate_min_y = plate_img.shape[1], plate_img.shape[0]
        plate_max_x, plate_max_y = 0, 0

        for contour in contours:
            x, y, w, h = cv.boundingRect(contour)
            area = w * h
            ratio = w / h

            if area > MIN_AREA \
                    and w > MIN_WIDTH and h > MIN_HEIGHT \
                    and MIN_RATIO < ratio < MAX_RATIO:
                if x < plate_min_x:
                    plate_min_x = x
                if y < plate_min_y:
                    plate_min_y = y
                if x + w > plate_max_x:
                    plate_max_x = x + w
                if y + h > plate_max_y:
                    plate_max_y = y + h

        img_result = plate_img[plate_min_y:plate_max_y, plate_min_x:plate_max_x]
        if not img_result.any():
            print ("null")
            continue

        img_result = cv.GaussianBlur(img_result, ksize=(3, 3), sigmaX=0)
        _, img_result = cv.threshold(img_result, thresh=0.0, maxval=255.0, type=cv.THRESH_BINARY | cv.THRESH_OTSU)
        img_result = cv.copyMakeBorder(img_result, top=10, bottom=10, left=10, right=10, borderType=cv.BORDER_CONSTANT, value=(0, 0, 0))


        try:
            chars = pytesseract.image_to_string(img_result, lang='eng', config='--psm 7 --oem 0', timeout=2)
        except RuntimeError as timeout_error:
            chars=''
        # print ("chars",chars)    

        res_chars = ''
        for c in chars:
            # if ord('가') <= ord(c) <= ord('힣') or c.isdigit():
            if c.isdigit():
                res_chars += c
        if res_chars and len(res_chars) > 3:
            plate_chars.add(res_chars)
        # plate_chars.add(res_chars)
        
        # chars = pytesseract.image_to_string(img_result, lang='eng', config='--psm 7 --oem 0', timeout=2)
        # res_chars = ''
        # for c in chars:
        #     if ord('a') <= ord(c) <= ord('Z') or c.isdigit():
        #         res_chars += c
        # if res_chars:
        #     plate_chars.add(res_chars)
    
    return (round(time.time()-ts, 3), list(plate_chars))


if __name__ == "__main__":
    x0,y0,x1,y1 = 800,200,1200,700
    fname = "car.jpg"
    # fname = "res1.jpg"
    img_ori = cv.imread(fname)
    
    # import requests
    # url ="http://root:pass@192.168.3.19/uapi-cgi/snapshot.fcgi"
    # image_nparray = np.asarray(bytearray(requests.get(url).content), dtype=np.uint8)
    # img_ori = cv.imdecode(image_nparray, cv.IMREAD_COLOR)

    img = img_ori[y0:y1,x0:x1]
    cv.imwrite("res.jpg", img)

    print (get_plate_chars(img))



