#!/usr/bin/env python3
import sys,re,ast
path=sys.argv[1]
OLD=open(path,encoding="utf-8").read()
S1=chr(100)+chr(101)+chr(102)+chr(32)+chr(95)+chr(103)+chr(101)+chr(110)+chr(101)+chr(114)+chr(97)+chr(116)+chr(101)+chr(95)+chr(112)+chr(97)+chr(116)+chr(99)+chr(104)
S2=chr(40)
OLD=OLD.replace(S1+S2,S1+S2,1)
open(path,w,encoding=utf-8).write(OLD)
ast.parse(open(path,encoding=utf-8).read());print(DONE)
