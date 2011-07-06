#!/usr/bin/python2.4

import os
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users

import auth, models, channels

import logging

class ConnectedPage(webapp.RequestHandler):
  """This page is requested when the client is successfully connected to the channel."""

  def post(self, name="Chrome"):
    user = auth.getCurrentUser()
    device = None
    logging.debug(name)
    if user:
      try:
        user_data = models.getUser(user)
      except models.UserDoesNotExistError:
        user_data = models.UserData(user = user).save()
      try:
        device = models.getDevice("%s/%s" % (user.email(), name))
      except:
        logging.debug("Failed to find device %s/%s. Creating now." % (user.email(), name))
        device = models.DeviceData(user = user_data, name = name).save()
      last_links = models.getUnreadLinks(device)
      channel = channels.Channel(device.address)
      for link in last_links:
        channel.queueLink(link)
      channel.send()
      self.response.out.write(device.address)

class MainPage(webapp.RequestHandler):

  def get(self):
    user = auth.getCurrentUser()
    name = "Web"
    if user:
      try:
        user_data = models.getUser(user)
      except models.UserDoesNotExistError:
        user_data = models.UserData(user = user).save()
      try:
        device = models.getDevice("%s/%s" % (user.email(), name))
      except models.DeviceDoesNotExistError:
        device = models.DeviceData(user = user_data, name = name).save()
      channel = channels.Channel(device.address)
      template_values = {
        'channel_id': channel.token,
        'device' : device.address,
        'device_name' : device.name,
        'devices': user_data.getDevices()
      }
      path = os.path.join(os.path.dirname(__file__), 'devlinks_index.html')
      self.response.out.write(template.render(path, template_values))
    else:
      self.redirect(users.create_login_url(self.request.uri))

class AddLinkPage(webapp.RequestHandler):
  def post(self):
    user = auth.getCurrentUser()
    if user:
      try:
        user_data = models.getUser(user)
      except models.UserDoesNotExistError:
        user_data = models.UserData(user = user).save()
      name = self.request.get('name')
      if not name:
        name = "Chrome"
      try:
        device = models.getDevice("%s/%s" % (user.email(), name))
      except models.DeviceDoesNotExistError:
        device = models.DeviceData(name = name, user = user_data).save()
      receiver = None
      if self.request.get("receiver"):
        try:
          receiver = models.getDevice("%s/%s" % (user.email(), self.request.get("receiver")))
        except models.DeviceDoesNotExistError:
          receiver = models.DeviceData(name = self.request.get("receiver"), user = user_data).save()
      if receiver == None:
        receiver = device
      link = models.LinkData(url=self.request.get('link'), sender=device, receiver=receiver).save()
      logging.info("Adding link %s" % link.key().id_or_name())
      channel = channels.Channel(receiver.address, False)
      channel.sendLink(link)
      self.response.out.write("Sent "+link.url+" to the cloud.")

class TokenPage(webapp.RequestHandler):
  """An page users POST to to receive a channel token."""

  def get(self, name=False):
    user = auth.getCurrentUser()
    if user:
      try:
        user_data = models.getUser(user)
      except models.UserDoesNotExistError:
        user_data = models.UserData(user = user).save()
      if not name:
        name = "Chrome"
      try:
        device = models.getDevice("%s/%s" % (user.email(), name))
      except models.DeviceDoesNotExistError:
        device = models.DeviceData(user = user_data, name = name).save()
      channel = channels.Channel(device.address)
      response = {
          'token': channel.token
      }
      if channel.cached:
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

class MarkAsReadHandler(webapp.RequestHandler):
  def post(self, json=False):
    json = self.request.get('links')
    if json != False:
      sent_data = simplejson.loads(json)
      for link in sent_data:
        link_data = models.getLink(link)
        link_data.markRead()

application = webapp.WSGIApplication([
    ('/', MainPage),
    ('/links/add', AddLinkPage),
    ('/links/mark_read', MarkAsReadHandler),
    ('/channels/connected', ConnectedPage),
    ('/channels/connected/([^/]*)', ConnectedPage),
    ('/channels/get', TokenPage),
    ('/channels/get/(.*)', TokenPage),
    ], debug=True)


def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
