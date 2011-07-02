from google.appengine.ext import db
from google.appengine.api import memcache
from datetime import datetime

class UserDoesNotExistError(Exception):
  account = None

  def __init__(self, account):
    self.account = account

  def __str__(self):
    return "UserDoesNotExistError: No account found for %s" % self.account.email()

class UserData(db.Model):
  """All the data we store with a given user."""
  user = db.UserProperty()
  display_name = db.StringProperty()
  joined = db.DateTimeProperty(auto_now_add=True)
  last_seen = db.DateTimeProperty(auto_now_add=True)
  
  def __init__(self, values):
    if values:
      if 'user' in values:
        self.user = values['user']
      else:
        self.user = auth.getCurrentUser()
      if 'display_name' in values:
        self.display_name = values['display_name']
      else:
        self.display_name = self.user.nickname()
      if 'joined' in values:
        self.joined = values['joined']
      if 'last_seen' in values:
        self.last_seen = values['last_seen']

  def updateLastSeen(self):
    self.last_seen = datetime.now()

  def save(self):
    self.put()
    memcache.set("user_%s_data" % self.user.user_id(), self)

  def get(account):
    user = memcache.get("user_%s_data", account.user_id())
    if user == None:
      user = UserData.all().filter("user =", account).get()
      if user == None:
        raise UserDoesNotExistError, user
      else:
        memcache.set("user_%s_data" % account.user_id(), user)
    return user

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
  
  def __init__(self, values):
    if values:
      if 'user' in values:
        self.user = values['user']
      else:
        account = auth.getCurrentUser()
        try:
          self.user = UserData.get(account)
        except UserDoesNotExistError, user:
          self.user = UserData({'user': user}).save()
      if 'name' in values:
        self.name = values['name']
      if 'address' in values:
        self.address = values['address']
      else:
        self.address = "%s/%s", (self.user.user.email(), self.name)

  def save(self):
    self.put()
    memcache.set("device_%s_data" % self.address, self)

  def get(address):
    device = memcache.get("device_%s_data" % address)
    if device == None:
      device = DeviceData.all().filter("address =", address).get()
      if device == None:
        raise DeviceDoesNotExistError, device
      else:
        memcache.set("device_%s_data" % address, device)
    return device

class LinkData(db.Model):
  url = db.StringProperty()
  date = db.DateTimeProperty(auto_now_add=True)
  sender = db.ReferenceProperty(DeviceData, collection_name="links_sent")
  receiver = db.ReferenceProperty(DeviceData, collection_name="links_received")
  received = db.BooleanProperty(default=False)

  def __init__(self, values):
    if values:
      if 'url' in values:
        self.url = values['url']
      if 'date' in values:
        self.date = values['date']
      if 'sender' in values:
        self.sender = values['sender']
      if 'receiver' in values:
        self.receiver = values['receiver']
      if 'received' in values:
        self.received = values['received']

  def save(self):
    self.put()

  def getUnread(device, count=1000):
    return device.links_received.filter("received =", False).fetch(count)

  def getByAccount(user, count=1000):
    return LinkData.all().filter("receiver IN", user.devices).fetch(count)
