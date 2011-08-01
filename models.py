from google.appengine.ext import db
from google.appengine.api import memcache, users
from django.utils import simplejson
from datetime import timedelta

import stats
import timestamp


class UserDoesNotExistError(Exception):
    account = None

    def __init__(self, account):
        self.account = account

    def __str__(self):
        return ("UserDoesNotExistError: No account found for %s" %
            self.account.email())


class UserData(db.Model):
    """All the data we store with a given user."""
    user = db.UserProperty()
    joined = db.DateTimeProperty(auto_now_add=True)
    last_seen = db.DateTimeProperty(auto_now_add=True)
    immunity = db.DateTimeProperty()
    immunity_tokens = db.IntegerProperty()

    def updateLastSeen(self):
        self.last_seen = timestamp.now()

    def save(self):
        try:
            self.key()
        except db.NotSavedError:
            stats.record("user_added",
                    simplejson.dumps({"user": self.user.email()}))
        self.put()
        memcache.set("user_%s_data" % self.user.user_id(), self)
        return self

    def getDevices(self):
        devices = memcache.get("user_%s_devices", self.user.user_id())
        if devices == None:
            devices = self.devices.fetch(1000)
            memcache.set("user_%s_devices" % self.user.user_id(), devices)
        return devices

    def setExplicitImmunity(self, stamp):
        self.immunity = stamp
        self.save()

    def setRelativeImmunity(self, offset):
        self.immunity = timestamp.now() + offset
        self.save()

    def incrementImmunityTokens(self, value=1):
        self.immunity_tokens = self.immunity_tokens + 1
        self.save()

    def setImmunityTokens(self, value):
        self.immunity_tokens = value
        self.save()

    def immune(self):
        if self.immunity is not None and self.immunity > timestamp.now():
            return True
        else:
            return False


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
    token = db.StringProperty()
    token_expiration = db.DateTimeProperty()

    def save(self):
        try:
            self.key()
        except db.NotSavedError:
            stats.record("device_added",
                    simplejson.dumps({"user": self.user.user.email(),
                        "device": self.address}))
        if self.address == None:
            self.address = "%s/%s" % (self.user.user.email(), self.name)
        self.put()
        memcache.set("device_%s_data" % self.address, self)
        return self

    def tokenValid(self):
        if self.token == None or self.token_expiration == None:
            return False
        current = timestamp.now()
        if self.token_expiration < current:
            return False
        else:
            return True

    def updateToken(self, token):
        self.token = token
        self.token_expiration = timestamp.now() + timedelta(hours=2)
        self.save()


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
    receiver = db.ReferenceProperty(DeviceData,
        collection_name="links_received")
    received = db.BooleanProperty(default=False)

    def save(self):
        try:
            self.key()
        except db.NotSavedError:
            stats.record("link_added", simplejson.dumps({
                "user": self.sender.user.user.email(),
                "link": self.url
            }))
        self.put()
        return self

    def markRead(self):
        self.received = True
        stats.record("link_opened", simplejson.dumps({
            "user": self.sender.user.user.email(),
            "link": self.url
        }))
        self.save()


class StatsData(db.Model):
    datapoint = db.StringProperty()
    count = db.IntegerProperty()
    date = db.DateTimeProperty()
    duration = db.StringProperty()

    def save(self):
        self.put()
        memcache.set("stats_%s_%s_%s" %
                (self.datapoint, self.date, self.duration), self)
        return self

    def increment(self):
        self.count = self.count + 1
        memcache.set("stats_%s_%s_%s" %
                (self.datapoint, self.date, self.duration), self)


class QuotaData(db.Model):
    date = db.DateTimeProperty()
    amount = db.IntegerProperty()


class PaymentData(db.Model):
    date = db.DateTimeProperty()
    user = db.ReferenceProperty(UserData, collection_name="payments")
    order_number = db.StringProperty()
    item = db.StringProperty()
    status = db.StringProperty()

    def save(self):
        self.put()
        stamp = timestamp.now()
        stamp = stamp.replace(day=stamp.day + 1, hour=0, minute=0, 
                second=0, microsecond=0)
        self.date = stamp
        self.user.setExplicitImmunity(stamp)
        stats.record("payment", simplejson.dumps({
            "user": self.user.user.email(),
            "item": self.item
        }))


class StatsSubscription(db.Model):
    event = db.StringProperty()
    datapoint = db.StringProperty()


def getUser(account, fromObject=True):
    if not fromObject:
        account = users.User(account)
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
    return (device.links_received.filter("received =", False)
        .order("-date").fetch(count))


def getLinksByAccount(user, count=1000):
    return (LinkData.all().filter("receiver IN", user.devices)
        .order("-date").fetch(count))


def getStats(datapoint, date=False, duration="day"):
    if not date:
        date = timestamp.now()
    if duration == 'day':
        date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif duration == 'hour':
        date = date.replace(minute=0, second=0, microsecond=0)
    else:
        return
    stats = memcache.get("stats_%s_%s_%s" % (datapoint, date, duration))
    if stats == None:
        stats = (StatsData.all().filter("datapoint =", datapoint)
            .filter("date =", date).filter("duration =", duration).get())
        if stats == None:
            stats = StatsData(datapoint=datapoint, date=date, count=0,
                    duration=duration)
            if datapoint == 'quota':
                stats.count = getQuota().amount
            stats.put()
        else:
            memcache.set("stats_%s_%s_%s" % (datapoint, date, duration),
                    stats)
    return stats


def getQuota():
    date = timestamp.now()
    quota = memcache.get("quota")
    if quota == None:
        quota = QuotaData.all().order("-date").get()
        if quota == None:
            quota = QuotaData(amount=0, date=date).put()
        memcache.set("quota", quota)
    return quota


def updateQuota(level):
    quota = QuotaData(amount=int(level), date=timestamp.now())
    quota.put()
    memcache.set("quota", quota)
    stats.record("quota_updated", str(quota.amount))
    return quota
