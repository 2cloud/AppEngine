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

class UserData(db.Model):
  """All the data we store with a given user."""
  user = db.UserProperty()
  display_name = db.StringProperty()
  joined = db.DateTimeProperty(auto_now_add=True)
  last_seen = db.DateTimeProperty(auto_now_add=True)

class DeviceData(db.Model):
  user = db.ReferenceProperty(UserData, collection_name="devices")
  name = db.StringProperty()
  address = db.StringProperty()
  default = db.BooleanProperty()

class FriendData(db.Model):
  requester = db.ReferenceProperty(UserData, collection_name="friends_requested")
  requested = db.ReferenceProperty(UserData, collection_name="friend_requests")
  approved = db.BooleanProperty()

class LinkData(db.Model):
  url = db.StringProperty()
  date = db.DateTimeProperty(auto_now_add=True)
  sender = db.ReferenceProperty(DeviceData, collection_name="links_sent")
  receiver = db.ReferenceProperty(DeviceData, collection_name="links_received")
  comment = db.TextProperty(required=False)
  instance = db.StringProperty(required=False, default="all")

class FederatedLinkData(db.Model):
  link = db.ReferenceProperty(LinkData)
  sending_server = db.StringProperty()
  receiving_server = db.StringProperty()
  sent = db.BooleanProperty()
  received = db.BooleanProperty()
  attempts = db.IntegerProperty()

class Maintainer(object):
  """Handles mundane adding/deletion/editing of models"""

  def __init__(self, identifier):
    models = {
      "device" : DeviceData,
      "link" : LinkData,
      "friend" : FriendData,
      "user" : UserData
    }
    self.identifier = identifier
    self.model = models[identifier]

  def new(self, values={}):
    obj = self.model()
    try:
      user = oauth.get_current_user()
    except:
      user = users.get_current_user()
    if self.identifier == "device":
      obj.user = memcache.get("user_%s_data", user.user_id())
      if obj.user == None:
        obj.user = UserData.all().filter("user =", user).get()
      if 'user' in values:
        obj.user = values['user']
      if obj.user == None:
        main = Maintainer("user")
        obj.user = db.get(main.new())
      memcache.set("user_%s_data" % obj.user.user.user_id(), obj.user)
      obj.name = "Chrome"
      if 'name' in values:
        obj.name = values['name']
      obj.address = "%s/%s" % (obj.user.user.email(), obj.name)
      if 'address' in values:
        obj.address = values['address']
      obj.default = True
      if 'default' in values:
        obj.default = values['default']
      memcache.set("device_%s_data" % obj.address, obj)
    elif self.identifier == "link":
      obj.url = "http://code.google.com/p/android2cloud/wiki/Welcome"
      if 'url' in values:
        obj.url = values['url']
      default_device = user.devices.order("default").get()
      obj.sender = default_device
      if 'sender' in values:
        obj.sender = values['sender']
      obj.receiver = default_device
      if 'receiver' in values:
        obj.receiver = values['receiver']
    elif self.identifier == "user":
      obj.user = user
      if 'user' in values:
        obj.user = values['user']
      obj.display_name = obj.user.nickname()
      if 'display_name' in values:
        obj.display_name = values['display_name']
      memcache.set("user_%s_data" % user.user_id(), obj)
    return obj.put()

class DeviceMessager(object):
  """Sends a message to a given device."""

  def __init__(self, receiver):
    self.receiver = memcache.get("device_%s_data" % receiver)
    if self.receiver == None:
      self.receiver = DeviceData.all().filter("address =", receiver).get()
    memcache.set("device_%s_data" % receiver, self.receiver)

  def CreateChannelToken(self):
    """Create a new channel token to let a client connect to a channel. We create
    a channel per device with the assumption that there is one client per device. More
    advanced applications could create more finely-grained channels to support multiple
    clients per device."""
    logging.info("Create channel: '" + self.receiver.address+"'")
    return channel.create_channel(self.receiver.address)
    #logging.info("Create channel: " + users.get_current_user().email() + "/Chrome")
    #return channel.create_channel(users.get_current_user().email() + "/Chrome")

  def Send(self, message):
    """Send a message to the designated device."""
    channel.send_message(self.receiver.address, simplejson.dumps(message))
    logging.info("Sending message to "+self.receiver.address+": "+simplejson.dumps(message))
    #channel.send_message(users.get_current_user().email() + "/Chrome", simplejson.dumps(message))
    #logging.info("Sending message to "+users.get_current_user().email() + "/Chrome")

  def SendLink(self, link, meta={}, silent=False):
    """Send a new link (LinkData) to a single device."""
    message = {'link' : {}, 'meta' : {}}
    message['link']['url'] = link.url
    #message['date'] = link.date
    link_sender = memcache.get("link_%s_sender" % link.key().id_or_name())
    if link_sender == None:
      link_sender = link.sender
      memcache.set("link_%s_sender" % link.key().id_or_name(), link_sender)
    message['link']['from'] = "%s (%s)" % (link_sender.user.display_name, link_sender.address)
    if link.comment:
      message['link']['comment'] = link.comment
    if link.instance:
      message['link']['instance'] = link.instance
    message['link']['id'] = link.key().id_or_name()
    if 'since_id' in meta:
      message['meta']['since_id'] = meta['since_id']
    else:
      message['meta']['since_id'] = message['link']['id']
    if silent:
      return message
    else:
      self.Send(message)
  
  def SendLinks(self, links, meta={}):
    """Send a group of links (LinkData) to a single device."""
    message = {'links' : {}, 'meta' : {}}
    for link in links:
      link_message = self.SendLink(link, meta, True)
      message['links'][link_message['link']['id']] = link_message
      message['meta']['links.latest'] = link.key().id_or_name()
    if not 'since_id' in meta and len(links) > 0:
      message['meta']['since_id'] = links[0].key().id_or_name()
    elif 'since_id' in meta and meta['since_id']['override']:
      message['meta']['since_id'] = meta['since_id']['id']
    self.Send(message)

class UserMessager(object):
  """Sends a message to all devices on a specified user's account."""

  def __init__(self, receiving_user):
    self.receiving_user = memcache.get("user_%s_data" % users.User(receiving_user).user_id())
    if self.receiving_user == None:
      self.receiving_user = UserData.all().filter("user =", users.User(receiving_user)).get()
    memcache.set("user_%s_data" % self.receiving_user.user.user_id(), self.receiving_user)

  def SendLink(self, link):
    """Send a new link (LinkData) to all devices on a specified user's account."""
    message = {'link' : {}}
    message['link']['url'] = link.url
    #message['date'] = link.date
    message['link']['from'] = "%s (%s)" % (link.sender.user.display_name, link.sender.address)
    if link.comment:
      message['link']['comment'] = link.comment
    for device in self.receiving_user.devices:
      messager = DeviceMessager(device.address)
      messager.Send(message)

class ConnectedPage(webapp.RequestHandler):
  """This page is requested when the client is successfully connected to the channel."""

  def post(self, name=False, since_id=False):
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
      if not since_id:
        last_links = device.links_received.order("date").fetch(1000)
        if len(last_links) != 0:
          last_link = last_links[0]
        else:
          last_link = False
      else:
        last_link = db.get(db.Key.from_path("LinkData", since_id))
        if last_link != None:
          last_links = device.links_received.order("-date").filter("date >", last_link.date).fetch(1000)
      if not last_link:
        last_link = LinkData()
        last_link.sender = device
        last_link.receiver = device
        last_link.url = "http://code.google.com/p/android2cloud/wiki/Welcome"
        last_link.put()
        last_links = [last_link]
      logging.info("last_link: "+last_link.url)
      meta = {'since_id' : {'id' : since_id, 'override' : False}}
      messager = DeviceMessager(device.address)
      logging.info("Sending "+last_link.url+" to "+messager.receiver.address)
      self.response.out.write(device.address)
      #latest_links = device.links_received.order("-date").filter("date >", last_link.data).fetch(1000), meta)
      messager.SendLinks(last_links, meta)

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
    if user:
      user_data = memcache.get("user_%s_data" % user.user_id())
      if user_data == None:
        user_data = UserData.all().filter("user =", user).get()
        memcache.set("user_%s_data" % user.user_id(), user_data)
      if user_data:
        instance = "all"
        if self.request.get("name"):
          device = memcache.get("device_%s/%s_data" % (user.email(), self.request.get("name")))
          if device == None:
            device = user_data.devices.filter("name =", self.request.get("name")).get()
          if not device:
            main = Maintainer("device")
            device = db.get(main.new({'name' : self.request.get("name"), 'default' : False}))
        else:
          device = memcache.get("user_%s_device" % user.user_id())
          if device == None:
            device = user_data.devices.order("default").get()
            memcache.set("user_%s_device" % user.user_id(), device)
        memcache.set("device_%s/%s_data" % (user.email(), device.name), device)
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
            recipient = main.new({'name' : address, 'default' : False})
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
        if not self.request.get("recipient"):
          messager = UserMessager(user.email())
        else:
          logging.info("Sending "+link.url+" to "+messager.receiver.address)
        messager.SendLink(link)

class TokenPage(webapp.RequestHandler):
  """An page users POST to to receive a channel token."""

  def get(self, name=False):
    user = False
    try:
      user = oauth.get_current_user()
    except oauth.InvalidOAuthTokenError, e:
      self.response.out.write("InvalidOAuthTokenError: %s" % e)
      user = users.get_current_user()
    except oauth.InvalidOAuthParametersError, e:
      self.response.out.write("InvalidOAuthParametersError: %s" % e.message)
      user = users.get_current_user()
    except oauth.InvalidOAuthRequestError, e:
      self.response.out.write("InvalidOAuthRequestError: %s" % e)
      user = users.get_current_user()
    except oauth.OAuthServiceFailureError, e:
      self.response.out.write("InvalidOAuthServiceError: %s" % e)
      user = users.get_current_user()
    except Exception, e:
      self.response.out.write("Exception: %s" % e)
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
      self.response.out.write(channel_token)
    else:
      self.response.out.write("Error: Not logged in.")

class ConfigHandler(webapp.RequestHandler):
  def get(self):
	settings = {'loginType': 'google',
				'secureHost' : 'https://android2cloud-dev.appspot.com/',
				'key' : 'android2cloud-dev.appspot.com',
				'secret' : 'IWWF240PCETzf92EFJDD1qH1',
				'callback' : 'callback/',
				'requestURL' : '_ah/OAuthGetRequestToken'}
	self.response.out.write(simplejson.dumps(settings))

application = webapp.WSGIApplication([
    ('/', MainPage),
    ('/addlink', AddLinkPage),
    ('/connected', ConnectedPage),
    ('/connected/([^/]*)', ConnectedPage),
    ('/connected/([^/]*)/([^/]*)', ConnectedPage),
    ('/getToken', TokenPage),
    ('/getToken/(.*)', TokenPage),
    ('/config', ConfigHandler)
    ], debug=True)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
