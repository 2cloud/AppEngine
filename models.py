#!/usr/bin/env python

from google.appengine.ext import db

class Link(db.Model):
    author = db.UserProperty()
    content = db.StringProperty(multiline=False)
    date = db.DateTimeProperty(auto_now_add=True)