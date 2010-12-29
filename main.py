#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api import users, oauth, memcache
from models import Link
import urllib2
from datetime import datetime

class MainHandler(webapp.RequestHandler):
    def get(self):
	#self.response.out.write("<html><head><meta name=\"google-site-verification\" content=\"LY2rJLPCIC-uYHvz2LA5ouB9iDPa_m1UIRTkvrHC0a0\" /></head><body></body></html>")
        self.redirect("http://code.google.com/p/android2cloud")

class RedirectHandler(webapp.RequestHandler):
    '''This class is built to handle redirection. It takes a URL, and redirects to that URL.'''
    def get(self, link):
        link = urllib2.unquote(link)
        self.response.out.write("Redirecting to " + link)
        self.redirect(link)

class AddLinkHandler(webapp.RequestHandler):
    '''This class is built to handle adding links. It takes a URL from a POST request, and displays that URL.'''
    def post(self):
        if users.get_current_user():
            link = Link()
            link.author = users.get_current_user()
            link.content = urllib2.quote(self.request.get('link'))
            link.put()
            memcache.set(link.author.user_id(), link)
            self.response.out.write("Sent %s to the cloud." % self.request.get('link'))
	elif oauth.get_current_user():
            link = Link()
            link.author = oauth.get_current_user()
            link.content = urllib2.quote(self.request.get('link'))
            link.put()
            memcache.set(link.author.user_id(), link)
            self.response.out.write("Sent %s to the cloud." % self.request.get('link'))
        else:
            self.redirect(users.create_login_url("/links/add"))
    
    def get(self):
        if users.get_current_user():
            self.response.out.write("<form method=\"post\"><input type=\"text\" name=\"link\"><input type=\"submit\"></form>")
        #elif oauth.get_current_user():
        #    self.response.out.write("<form method=\"post\"><input type=\"text\" name=\"link\"><input type=\"submit\"></form>")
        else:
            self.redirect(users.create_login_url("/links/add"))

class GetLinkHandler(webapp.RequestHandler):
    '''This class is built to handle returning the latest URL added. It takes no arguments, and returns a URL.'''
    def get(self):
        if users.get_current_user():
            link = Link.all().filter("author =", users.get_current_user()).order("-date").get()
            if link and link.content:
                self.response.out.write("<link>" + urllib2.unquote(link.content) + "</link>")
            else:
                self.response.out.write("\"\"")
        #elif oauth.get_current_user():
        #if oauth.get_current_user():
        #    user = oauth.get_current_user()
        #    source = "memcache"
        #    link = memcache.get(user.user_id())
        #    if link is None:
        #       link = Link.all().filter("author =", oauth.get_current_user()).order("-date").get()
        #        source = "database"
        #    if link and link.content:
		#timedelta = datetime.now() - link.date
        #        self.response.out.write("<link>" + urllib2.unquote(link.content) + "</link><source>" + source +"</source><age>" + str(timedelta.days) + "</age>")
        #    else:
        #        self.response.out.write("\"\"")
        else:
            #self.redirect(users.create_login_url("/links/get"))
            self.response.out.write("Not logged in...")

class AllLinksHandler(webapp.RequestHandler):
    '''This class is built to handle returning the authenticated users's added link. It takes no arguments, and returns a list of 100 links.'''
    def get(self):
        if users.get_current_user():
            links = Link.all().filter("author =", users.get_current_user()).order("-date").fetch(100)
            self.response.out.write("<ul>")
            for link in links:
                if link and link.content:
                    self.response.out.write("<li><a href=\"" + urllib2.unquote(link.content) + "\">" + urllib2.unquote(link.content)+ "</li>")
            self.response.out.write("</ul>")
        else:
            self.redirect(users.create_login_url("/links/all"))

def main():
    application = webapp.WSGIApplication([('/', MainHandler),
                                          ('/go/(.*)', RedirectHandler),
                                          ('/links/add', AddLinkHandler),
                                          ('/links/get', GetLinkHandler),
                                          ('/links/all', AllLinksHandler)],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
