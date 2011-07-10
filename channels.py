from django.utils import simplejson
from google.appengine.api import channel, memcache

import models
import stats


class OverQuotaError(Exception):

    def __str__(self):
        return "App is currently over quota. Please wait until tomorrow."


class Channel():
    token = None
    address = None
    cached = True
    message = {}

    def __init__(self, address, generate=True, override_quota=False):
        self.address = address
        if generate:
            self.token = memcache.get("token_%s" % self.address)
            if self.token is None:
                device = models.getDevice(self.address)
                if device.token and device.tokenValid():
                    self.token = device.token
                else:
                    if models.getQuota().amount > models.getStats(
                            'channels').count or override_quota:
                        self.token = channel.create_channel(self.address)
                        stats.record("channel_created", simplejson.dumps({
                            "channel": self.address}))
                        self.cached = False
                        device.updateToken(self.token)
                    else:
                        raise OverQuotaError()
                        return False
                memcache.set("token_%s" % self.address, self.token, time=7200)

    def send(self):
        channel.send_message(self.address, simplejson.dumps(self.message))
        self.message.clear()

    def queueLink(self, link):
        if 'links' not in self.message:
            self.message['links'] = []
        link_message = {}
        link_message['id'] = link.key().id_or_name()
        link_message['url'] = link.url
        link_message['sender'] = link.sender.address
        self.message['links'].append(link_message)

    def sendLink(self, link):
        self.queueLink(link)
        self.send()
