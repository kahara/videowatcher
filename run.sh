#!/bin/sh

./videowatcher.py --camera http://192.168.0.168/image.jpg --interval 1 --width 320 --height 240 --references 10 --mindiff 16 --mintotal 1000 --bucket videowatcher --region eu-west-1 --topic arn:aws:sns:eu-west-1:187166072501:videowatcher
