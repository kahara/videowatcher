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
from PIL import Image, ImageFilter
import StringIO
import time
from boto.s3.bucket import Bucket
from boto.s3.key import Key
import boto.sns
import threading
import datetime

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(description=__doc__, version="v%s" % __version__)
    
    parser.add_argument('-u', '--username', action='store', dest='username', default=None, required=False, help='HTTP Basic auth username, if required')
    parser.add_argument('-p', '--password', action='store', dest='password', default=None, required=False, help='HTTP Basic auth password, if required')
    parser.add_argument('-c', '--camera', action='store', dest='camera', default=None, required=True, help='Camera image URL')
    parser.add_argument('-i', '--interval', action='store', dest='interval', type=int, default=5, required=False, help='Frame capture interval')
    parser.add_argument('-x', '--width', action='store', dest='width', type=int, default=320, required=False, help='Frame width')
    parser.add_argument('-y', '--height', action='store', dest='height', type=int, default=240, required=False, help='Frame height')
    parser.add_argument('-b', '--bucket', action='store', dest='bucket', default=None, required=False, help='S3 bucket to upload images to')
    parser.add_argument('-r', '--region', action='store', dest='region', default=None, required=False, help='SNS region to connect to')
    parser.add_argument('-t', '--topic', action='store', dest='topic', default=None, required=False, help='SNS topic to publish notifications to')
    
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

    class ImageUploader(threading.Thread):
        def __init__(self, image=None):
            threading.Thread.__init__(self)
            self.image = image.tostring('jpeg', 'RGB')

        def run(self):
            connection = boto.connect_s3()
            bucket = Bucket(connection, 'videowatcher')
            key = Key(bucket)
            key.key = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S') + '.jpg'
            key.set_contents_from_string(self.image, headers={'Content-Type': 'image/jpeg'})
            
            url = key.generate_url(31536000)
            print url
            sns = boto.sns.connect_to_region(args.region)
            sns.publish(args.topic, url)
            
    reference = fetch().convert('L')
    
    def handler(signum, frame):
        in_image = fetch()
        image = in_image.convert('L')
        image = image.filter(ImageFilter.GaussianBlur(radius=5))
        
        image_data = image.load()
        reference_data = reference.load()
        
        diff = 0
        for y in range(args.height):
            for x in range(args.width):
                diff += 1 if abs(reference_data[x, y]-image_data[x, y]) > 5 else 0
        reference.paste(image)

        if diff > 1000:
            print diff
            imageuploader = ImageUploader(image=in_image)
            imageuploader.start()
    
    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 2, 2)

    while True:
        time.sleep(0.01)
