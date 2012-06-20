#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Load still JPEG frames from IP camera, upload to S3 and send SNS notification on change"""

__appname__ = "videowatcher"
__author__  = "Joni Kähärä (kahara)"
__version__ = "0.0pre0"
__license__ = "GNU GPL 3.0 or later"

import urllib, httplib2, base64
import argparse
import signal
from PIL import Image, ImageMath
import StringIO

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(description=__doc__, version="v%s" % __version__)
    
    parser.add_argument('-u', '--username', action='store', dest='username', default=None, required=False, help='HTTP Basic auth username, if required')
    parser.add_argument('-p', '--password', action='store', dest='password', default=None, required=False, help='HTTP Basic auth password, if required')
    parser.add_argument('-c', '--camera', action='store', dest='camera', default=None, required=True, help='Camera image URL')
    parser.add_argument('-i', '--interval', action='store', dest='interval', type=int, default=5, required=False, help='Frame capture interval')
    parser.add_argument('-x', '--width', action='store', dest='width', type=int, default=320, required=False, help='Frame width')
    parser.add_argument('-y', '--height', action='store', dest='height', type=int, default=240, required=False, help='Frame height')
    
    args  = parser.parse_args()

    if not args.camera:
        parser.print_help()
        exit()
        
    http = httplib2.Http()
    if args.username and args.password:
        headers = { 'Authorization' : 'Basic ' + base64.encodestring(args.username + ':' + args.password) }
    else:
        headers = None

    url = args.camera
        
    def fetch():
        if headers:
            response, content = http.request(url, 'GET', headers)
        else:
            response, content = http.request(url, 'GET')
        
        if response['status'] == '200':
            return Image.open(StringIO.StringIO(content))
        else:
            return None
    
    def handler():
        image = fetch()
        
        image_data = image.load()
        reference_data = reference.load()
        
        diff = 0
        for y in range(args.height):
            for x in range(args.width):
                reference_pixel = reference_data[x, y]
                image_pixel = image_data[x, y]
                diff += abs(reference_pixel[0]-image_pixel[0]) + abs(reference_pixel[1]-image_pixel[1]) + abs(reference_pixel[2]-image_pixel[2])
        
        reference.paste(image)
        
        print diff
    
    reference = fetch()
    
    for i in range(1000):
        handler()
