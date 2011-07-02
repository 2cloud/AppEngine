#!/usr/bin/python2.4

import datetime
import logging
import os
import random
from django.utils import simplejson
from google.appengine.api import users, oauth, channel, memcache
from google.appengine.ext import db, webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

class ConnectedPage(webapp.RequestHandler):
  """This page is requested when the client is successfully connected to the channel."""

  def post(self, name=False):
    try:
      user = oauth.get_current_user()
    except:
      user = users.get_current_user()
    if user:
      user_data = memcache.get("user_%s_data" % user.user_id())
      if not user_data:
        user_data = UserData.all().filter("user =", user).get()
        logging.info("memcache failed... 196")
        if user_data == None:
          user_data = UserData()
          user_data.user = user
          user_data.display_name = user.nickname()
          user_data.put()
          device = DeviceData()
          device.user = user_data
          device.name = "Chrome"
          device.address = "%s/%s" % (user.email(), chrome.name)
          device.default = True
          device.put()
      memcache.set("user_%s_data" % user.user_id(), user_data)
      if name:
        device = memcache.get("device_%s/%s_data" % (user.email(), name))
        logging.info("215")
      else:
        device = memcache.get("user_%s_device" % user.user_id())
        logging.info("218")
      if device == None:
        logging.info("memcache failed... 217")
        if name:
          device = user_data.devices.filter("name =", name).get()
          logging.info("223")
          if device == None:
            device = DeviceData()
            device.user = user_data
            device.name = name
            device.address = "%s/%s" % (user.email(), chrome.name)
            device.default = True
            device.put()
            logging.info("231")
        else:
          device = user_data.devices.filter("default =", True).get()
          logging.info("234")
      memcache.set("user_%s_device" % user.user_id(), device)
      memcache.set("device_%s_data" % device.address, device)
      logging.info("device: "+device.address)
      last_links = device.links_received.order("-date").filter("received =", False).fetch(1000)
      messager = DeviceMessager(device.address)
      self.response.out.write(device.address)
      #latest_links = device.links_received.order("-date").filter("date >", last_link.data).fetch(1000), meta)
      if last_links != None:
        messager.SendLinks(last_links, {})
      
class MainPage(webapp.RequestHandler):
  """The main UI page, renders the 'index.html' template."""

  def get(self):
    """Renders the main page. When this page is shown, we create a new
    channel to push asynchronous updates to the client."""
    try:
      user = oauth.get_current_user()
    except:
      user = users.get_current_user()
    override = {}
    if self.request.get("display_name"):
      override['display_name'] = self.request.get("display_name")
    if self.request.get("name"):
      override['name'] = self.request.get("name")
    if self.request.get("flush_memcache"):
      memcache.flush_all()
    if user:
      user_data = UserData.all().filter("user =", user).get()
      if not user_data:
        main = Maintainer("user")
        user_data = db.get(main.new(override))
      if self.request.get("name"):
        device = user_data.devices.filter("name =", self.request.get("name")).get()
      else:
        device = user_data.devices.order("default").get()
      if not device:
        main = Maintainer("device")
        device = db.get(main.new(override))
      messager = DeviceMessager(device.address)
      logging.info(messager.receiver.address)
      channel_token = messager.CreateChannelToken()
      template_values = {
        'channel_id': channel_token,
        'device' : device.address,
        'device_name' : device.name
      }
      path = os.path.join(os.path.dirname(__file__), 'devlinks_index.html')
      self.response.out.write(template.render(path, template_values))
    else:
      self.redirect(users.create_login_url(self.request.uri))

class AddLinkPage(webapp.RequestHandler):
  """An unseen page users POST to to add a link."""
  def post(self):
    try:
      user = oauth.get_current_user()
    except:
      user = users.get_current_user()
    if not user:
      self.response.out.write("Had a problem logging you in. Please log out and log back in.")
    if user:
      logging.info("User "+user.email())
      user_data = memcache.get("user_%s_data" % user.user_id())
      if user_data == None:
        logging.info("328")
        user_data = UserData.all().filter("user =", user).get()
        memcache.set("user_%s_data" % user.user_id(), user_data)
      logging.info("user_data check")
      if not user_data:
        main = Maintainer("user")
        user_data = db.get(main.new({}))
      if user_data:
        logging.info("user_data_found")
        instance = "all"
        if self.request.get("name"):
          logging.info("335")
          device = memcache.get("device_%s/%s_data" % (user.email(), self.request.get("name")))
          if device == None:
            device = user_data.devices.filter("name =", self.request.get("name")).get()
          if not device:
            main = Maintainer("device")
            device = db.get(main.new({'name' : self.request.get("name"), 'default' : False}))
            logging.info("342")
        else:
          device = memcache.get("user_%s_device" % user.user_id())
          if device == None:
            device = user_data.devices.order("default").get()
            memcache.set("user_%s_device" % user.user_id(), device)
        memcache.set("device_%s/%s_data" % (user.email(), device.name), device)
        logging.info(device.name)
        if self.request.get("recipient"):
          address = self.request.get("recipient").replace("%40", "@").replace("%2F", "/")
          if address.find("/") == -1:
            address = user.email() + "/" + address
          logging.info(address)
          if address.find(":") != -1:
            instance = address.split(":")[1]
            address = address.split(":")[0]
          recipient = memcache.get("device_%s_data" % address)
          logging.info("334")
          if recipient == None:
            recipient = DeviceData.all().filter("address =", address).get()
            logging.info("336")
          if not recipient:
            main = Maintainer("device")
            logging.info("338")
            recipient = db.get(main.new({'name' : address, 'default' : False}))
          memcache.set("device_%s_data" % recipient.address, recipient)
        else:
          recipient = device
          logging.info("345")
        link = LinkData()
        link.sender = device
        link.receiver = recipient
        link.url = self.request.get('link')
        link.comment = self.request.get("comment")
        link.instance = instance
        link.put()
        memcache.set("link_%s_sender" % link.key().id_or_name(), link.sender)
        messager = DeviceMessager(recipient.address)
        logging.info("Sending "+link.url+" to "+messager.receiver.address)
        messager.SendLinks([link])
        self.response.out.write("Sent "+link.url+" to the cloud.")

class TokenPage(webapp.RequestHandler):
  """An page users POST to to receive a channel token."""

  def get(self, name=False):
    user = False
    try:
      user = oauth.get_current_user()
    except oauth.InvalidOAuthTokenError, e:
      #self.response.out.write("InvalidOAuthTokenError: %s" % e)
      user = users.get_current_user()
    except oauth.InvalidOAuthParametersError, e:
      #self.response.out.write("InvalidOAuthParametersError: %s" % e.message)
      user = users.get_current_user()
    except oauth.InvalidOAuthRequestError, e:
      #self.response.out.write("InvalidOAuthRequestError: %s" % e)
      user = users.get_current_user()
    except oauth.OAuthServiceFailureError, e:
      #self.response.out.write("InvalidOAuthServiceError: %s" % e)
      user = users.get_current_user()
    except Exception, e:
      #self.response.out.write("Exception: %s" % e)
      user = users.get_current_user()
    override = {}
    if name:
      override['name'] = name
    if user:
      user_data = memcache.get("user_%s_data" % user.user_id())
      if user_data == None:
        user_data = UserData.all().filter("user =", user).get()
      if not user_data:
        main = Maintainer("user")
        user_data = db.get(main.new(override))
      memcache.set("user_%s_data" % user.user_id(), user_data)
      if name:
        device = memcache.get("device_%s/%s_data" % (user.email(), name))
        if device == None:
          device = user_data.devices.filter("name =", name).get()
      else:
        device = memcache.get("user_%s_device" % user.user_id())
        if device == None:
          device = user_data.devices.order("default").get()
      if not device:
        main = Maintainer("device")
        device = db.get(main.new(override))
      memcache.set("device_%s_data" % device.address, device)
      memcache.set("user_%s_device" % user.user_id(), device)
      messager = DeviceMessager(device.address)
      logging.info(messager.receiver.address)
      channel_token = messager.CreateChannelToken()
      response = {
          'token': channel_token['token']
      }
      if channel_token['cached']:
        response['code'] = 304
      else:
        response['code'] = 200
      self.response.out.write(simplejson.dumps(response))
    else:
      response = {
          'code': 401,
          'message': 'Not logged in.'
      }
      self.response.out.write(simplejson.dumps(response))

class NewMarkAsReadHandler(webapp.RequestHandler):
  def post(self, json=False):
    json = self.request.get('links')
    if json != False:
      sent_data = simplejson.loads(json)
      for link in sent_data:
        logging.info(link)
        link_object = LinkData.get_by_id(int(link))
        link_object.received = True
        link_object.put()

class MarkAsReadHandler(webapp.RequestHandler):
  def post(self, json=False):
    json = self.request.get('links')
    if json != False:
      sent_data = simplejson.loads(json)
      try:
        sent_data['links']
      except KeyError:
        sent_data['links'] = None
        
      try:
        sent_data['link']
      except KeyError:
        sent_data['link'] = None
    
    if sent_data['link'] is not None:
      link_object = LinkData.get_by_id(int(sent_data['link']['id']))
      link_object.received = True
      link_object.put()
    
    if sent_data['links'] is not None:
      for link in sent_data['links']:
        logging.info(link)
        logging.info(sent_data['links'][link])
        link_object = LinkData.get_by_id(int(sent_data['links'][link]['link']['id']))
        link_object.received = True
        link_object.put()


application = webapp.WSGIApplication([
    ('/', MainPage),
    ('/addlink', AddLinkPage),
    ('/markread', MarkAsReadHandler),
    ('/marklinkread', NewMarkAsReadHandler),
    ('/connected', ConnectedPage),
    ('/connected/([^/]*)', ConnectedPage),
    ('/connected/([^/]*)/([^/]*)', ConnectedPage),
    ('/getToken', TokenPage),
    ('/getToken/(.*)', TokenPage),
    ('/config', ConfigHandler),
    ('/links/(.*)', UpgradePage)
    ], debug=True)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
