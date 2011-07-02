from google.appengine.ext import db
from google.appengine.api import memcache
from datetime import datetime

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

  def getUser(account):
    user = memcache.get("user_%s_data", account.user_id())
    if user == None:
      user = UserData.all().filter("user =", account).get()
      if user == None:
        raise UserDoesNotExistError, user
      else:
        memcache.set("user_%s_data" % account.user_id(), user)
    return user

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
          self.user = UserData.getUser(account)
        except UserDoesNotExistError, user:
          self.user = UserData({'user': user}).put()
      if 'name' in values:
        self.name = values['name']
      if 'address' in values:
        self.address = values['address']
      else:
        self.address = "%s/%s", (self.user.user.email(), self.name)

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
