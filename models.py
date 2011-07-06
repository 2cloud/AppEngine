from google.appengine.ext import db
from google.appengine.api import memcache
from datetime import datetime

import logging

class UserDoesNotExistError(Exception):
  account = None

  def __init__(self, account):
    self.account = account

  def __str__(self):
    return "UserDoesNotExistError: No account found for %s" % self.account.email()

class UserData(db.Model):
  """All the data we store with a given user."""
  user = db.UserProperty()
  joined = db.DateTimeProperty(auto_now_add=True)
  last_seen = db.DateTimeProperty(auto_now_add=True)

  def updateLastSeen(self):
    self.last_seen = datetime.now()

  def save(self):
    self.put()
    memcache.set("user_%s_data" % self.user.user_id(), self)
    return self

  def getDevices(self):
    devices = memcache.get("user_%s_devices", self.user.user_id())
    if devices == None:
      devices = self.devices.fetch(1000)
      memcache.set("user_%s_devices" % self.user.user_id(), devices)
    return devices

class DeviceDoesNotExistError(Exception):
  address = None

  def __init__(self, address):
    self.address = address

  def __str__(self):
    return "DeviceDoesNotExistError: No device found for %s" % self.address

class DeviceData(db.Model):
  user = db.ReferenceProperty(UserData, collection_name="devices")
  name = db.StringProperty()
  address = db.StringProperty()
  
  def save(self):
    if self.address == None:
      self.address = "%s/%s" % (self.user.user.email(), self.name)
    self.put()
    memcache.set("device_%s_data" % self.address, self)
    return self

class LinkDoesNotExistError(Exception):
  id_or_name = None

  def __init__(self, id_or_name):
    self.id_or_name = id_or_name

  def __str__(self):
    return "LinkDoesNotExistError: No link found for %s" % self.id_or_name

class LinkData(db.Model):
  url = db.StringProperty()
  date = db.DateTimeProperty(auto_now_add=True)
  sender = db.ReferenceProperty(DeviceData, collection_name="links_sent")
  receiver = db.ReferenceProperty(DeviceData, collection_name="links_received")
  received = db.BooleanProperty(default=False)

  def save(self):
    self.put()
    return self

  def markRead(self):
    self.received = True
    self.save()

def getUser(account):
  user = memcache.get("user_%s_data", account.user_id())
  if user == None:
    user = UserData.all().filter("user =", account).get()
    if user == None:
      raise UserDoesNotExistError(user)
    else:
      memcache.set("user_%s_data" % account.user_id(), user)
  return user

def getDevice(address):
  device = memcache.get("device_%s_data" % address)
  if device == None:
    device = DeviceData.all().filter("address =", address).get()
    if device == None:
      raise DeviceDoesNotExistError(device)
    else:
      memcache.set("device_%s_data" % address, device)
  return device

def getLink(id_or_name):
  link = LinkData.get_by_id(int(id_or_name))
  if link == None:
    raise LinkDoesNotExistError(id_or_name)
  else:
    return link

def getUnreadLinks(device, count=1000):
  return device.links_received.filter("received =", False).order("-date").fetch(count)

def getLinksByAccount(user, count=1000):
  return LinkData.all().filter("receiver IN", user.devices).order("-date").fetch(count)
