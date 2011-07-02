from django.utils import simplejson
from google.appengine.api import channel, memcache

class Channel():
  token = None
  address = None
  cached = True
  message = {}

  def __init__(self, address):
   self.address = address
   self.token = memcache.get("token_%s" % self.address)
   if self.token is None:
     self.token = channel.create_channel(self.address)
     self.cached = False
     memcache.set("token_%s" % self.address, self.token, time=7200)

  def send(self):
    channel.send_message(self.address, simplejson.dumps(self.message))

  def queueLink(self, link):
    if 'links' not in self.message:
      self.message['links'] = []
    link_message = {}
    link_message['id'] = link.key().id_or_name()
    link_message['url'] = link.url
    link_message['sender'] = link.sender.address
    self.message['links'].push(link_message)

  def sendLink(self, link):
    self.queueLink(link)
    self.send()
