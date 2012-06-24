#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Load still JPEG frames from IP camera, on change upload to S3 and send SNS notification"""

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
import math

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(description=__doc__, version="v%s" % __version__)
    
    parser.add_argument('-u', '--username', action='store', dest='username', default=None, required=False, help='HTTP Basic auth username, if required')
    parser.add_argument('-p', '--password', action='store', dest='password', default=None, required=False, help='HTTP Basic auth password, if required')
    parser.add_argument('-c', '--camera', action='store', dest='camera', default=None, required=True, help='Camera image URL')
    parser.add_argument('-i', '--interval', action='store', dest='interval', type=int, default=1, required=False, help='Frame capture interval')
    parser.add_argument('-x', '--width', action='store', dest='width', type=int, default=320, required=False, help='Frame width')
    parser.add_argument('-y', '--height', action='store', dest='height', type=int, default=240, required=False, help='Frame height')
    parser.add_argument('-n', '--references', action='store', dest='references', type=int, default=5, required=False, help='How many frames to use as reference when figuring out image changes')
    parser.add_argument('-m', '--mindiff', action='store', dest='mindiff', type=int, default=16, required=False, help='Minimum difference between a pixel in incoming image and reference to count as changed')
    parser.add_argument('-a', '--mintotal', action='store', dest='mintotal', type=int, default=1000, required=False, help='Minimum number of "mindiff" pixels to trigger image upload and notification publishing')
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
        def __init__(self, image=None, bucket=None, region=None, topic=None):
            threading.Thread.__init__(self)
            self.image = image.tostring('jpeg', 'RGB')
            self.bucket = bucket
            self.region = region
            self.topic = topic

        def run(self):
            connection = boto.connect_s3()
            bucket = Bucket(connection, self.bucket)
            key = Key(bucket)
            key.key = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S') + '.jpg'
            key.set_contents_from_string(self.image, headers={'Content-Type': 'image/jpeg'})
            print 'uploaded:', key.key
            
            if self.region and self.bucket:
                url = key.generate_url(31536000)
                sns = boto.sns.connect_to_region(self.region)
                sns.publish(self.topic, url)
                print 'published:', self.topic, url
                
    references = []
    
    def handler(signum, frame):
        global references
        
        in_image = fetch()
        image = in_image.convert('L')
        image = image.filter(ImageFilter.GaussianBlur(radius=3))
        
        if len(references) >= args.references:
            references.pop()
        references.insert(0, image.load())
        
        if len(references) < args.references:
            print 'collecting references...'
            return
        
        image_data = image.load()
        total = 0
        for y in range(args.height):
            for x in range(args.width):
                values = []
                for reference in references:
                    values.append(reference[x, y])
                
                skip = int(math.floor(len(values)/2.5))
                values = sorted(values)[:-skip]
                avg = sum(values)/len(values)
                
                diff = abs(image_data[x, y]-avg)
                total += 1 if diff >= args.mindiff else 0
                
        print total
        
        if total >= args.mintotal:
            references = []
            if args.bucket:
                imageuploader = ImageUploader(image=in_image, bucket=args.bucket, region=args.region, topic=args.topic)
                imageuploader.start()
    
    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, args.interval, args.interval)

    while True:
        time.sleep(0.01)
