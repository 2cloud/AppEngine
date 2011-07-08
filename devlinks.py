#!/usr/bin/python2.4

import os
from django.utils import simplejson
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users, prospective_search

import auth
import models
import channels
import stats

import logging


class ConnectedPage(webapp.RequestHandler):

    def post(self, name="Chrome"):
        user = auth.getCurrentUser()
        device = None
        if user:
            try:
                user_data = models.getUser(user)
            except models.UserDoesNotExistError:
                user_data = models.UserData(user=user).save()
            try:
                device = models.getDevice("%s/%s" % (user.email(), name))
            except:
                device = models.DeviceData(user=user_data, name=name).save()
            last_links = models.getUnreadLinks(device)
            channel = channels.Channel(device.address)
            for link in last_links:
                channel.queueLink(link)
            channel.send()
            stats.record("user_connected", user.email())
            self.response.out.write(device.address)


class MainPage(webapp.RequestHandler):

    def get(self):
        user = auth.getCurrentUser()
        name = "Web"
        if user:
            try:
                user_data = models.getUser(user)
            except models.UserDoesNotExistError:
                user_data = models.UserData(user=user).save()
            try:
                device = models.getDevice("%s/%s" % (user.email(), name))
            except models.DeviceDoesNotExistError:
                device = models.DeviceData(user=user_data, name=name).save()
            channel = channels.Channel(device.address)
            template_values = {
                'channel_id': channel.token,
                'device': device.address,
                'device_name': device.name,
                'devices': user_data.getDevices()
            }
            path = os.path.join(os.path.dirname(__file__),
                'devlinks_index.html')
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
                user_data = models.UserData(user=user).save()
            name = self.request.get('name')
            if not name:
                name = "Chrome"
            try:
                device = models.getDevice("%s/%s" % (user.email(), name))
            except models.DeviceDoesNotExistError:
                device = models.DeviceData(name=name, user=user_data).save()
            receiver = None
            if self.request.get("receiver"):
                try:
                    receiver = models.getDevice("%s/%s" % (user.email(),
                      self.request.get("receiver")))
                except models.DeviceDoesNotExistError:
                    receiver = models.DeviceData(
                        name=self.request.get("receiver"),
                        user=user_data).save()
            if receiver == None:
                receiver = device
            link = models.LinkData(url=self.request.get('link'),
                sender=device, receiver=receiver).save()
            channel = channels.Channel(receiver.address, False)
            channel.sendLink(link)
            self.response.out.write("Sent " + link.url + " to the cloud.")


class TokenPage(webapp.RequestHandler):

    def get(self, name=False):
        user = auth.getCurrentUser()
        if user:
            try:
                user_data = models.getUser(user)
            except models.UserDoesNotExistError:
                user_data = models.UserData(user=user).save()
            if not name:
                name = "Chrome"
            try:
                device = models.getDevice("%s/%s" % (user.email(), name))
            except models.DeviceDoesNotExistError:
                device = models.DeviceData(user=user_data, name=name).save()
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


class SubscribeHandler(webapp.RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'subscribe.html')
        self.response.out.write(template.render(path, {}))

    def post(self):
        event = self.request.POST['event']
        datapoint = self.request.POST['datapoint']
        subscription_id = models.StatsSubscription(event=event,
            datapoint=datapoint).put()
        prospective_search.subscribe(stats.StatsRecord, 'event:%s' % event,
            subscription_id)
        self.response.out.write("Subscribed the datapoint %s to %s events." %
            (datapoint, event))


class StatsHandler(webapp.RequestHandler):
    def post(self):
        record = prospective_search.get_document(self.request)
        subscriber_keys = map(db.Key, self.request.get_all('id'))
        subscribers = db.get(subscriber_keys)
        datapoints = []
        stats_json = []
        for subscriber_key, subscriber in zip(subscriber_keys, subscribers):
            if not subscriber:
                prospective_search.unsubscribe(stats.StatsRecord,
                    subscriber_key)
            else:
                datapoints.append(models.getStats(subscriber.datapoint,
                  record.timestamp.date()))
        for datapoint in datapoints:
            datapoint.increment()
            day = record.timestamp.date()
            date = "%s/%s/%s" % (day.month, day.day, day.year)
            json = {'datapoint': datapoint.datapoint, 'count': datapoint.count,
                'date': date}
            stats_json.append(json)
        db.put(datapoints)
        logging.debug(simplejson.dumps(stats_json))


application = webapp.WSGIApplication([
        ('/', MainPage),
        ('/links/add', AddLinkPage),
        ('/links/mark_read', MarkAsReadHandler),
        ('/channels/connected', ConnectedPage),
        ('/channels/connected/([^/]*)', ConnectedPage),
        ('/channels/get', TokenPage),
        ('/channels/get/(.*)', TokenPage),
        ('/stats/subscribe', SubscribeHandler),
        ('/_ah/prospective_search', StatsHandler)
        ], debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
