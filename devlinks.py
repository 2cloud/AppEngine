#!/usr/bin/python2.4

import os
from django.utils import simplejson
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import users, prospective_search
import time

import auth
import models
import channels
import stats
import timestamp

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
            channel = channels.Channel(device.address, False)
            for link in last_links:
                channel.queueLink(link)
            channel.send()
            stats.record("user_connected",
                    simplejson.dumps({"user": user.email()}))
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
            over_quota = False
            try:
                channel = channels.Channel(device.address,
                        override_quota=user_data.immune())
                channel_token = channel.token
            except channels.OverQuotaError:
                over_quota = True
                channel_token = 'overquota'
            template_values = {
                'channel_id': channel_token,
                'device': device.address,
                'device_name': device.name,
                'devices': user_data.getDevices(),
                'over_quota': over_quota
            }
            path = os.path.join(os.path.dirname(__file__),
                'devlinks_index.html')
            self.response.out.write(template.render(path, template_values))
        else:
            self.redirect(users.create_login_url(self.request.uri))


class AddLinkPage(webapp.RequestHandler):
    def post(self):
        user = auth.getCurrentUser()
        response = {}
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
            if models.getQuota().amount >= models.getStats(
                    'channels').count or user_data.immune():
                channel = channels.Channel(receiver.address, False)
                channel.sendLink(link)
                response['code'] = 200
                response['link'] = link.url
            else:
                response['code'] = 503
                response['link'] = link.url
        else:
            response['code'] = 401
            response['link'] = self.request.get('link')
        self.response.out.write(simplejson.dumps(response))


class TokenPage(webapp.RequestHandler):
    def get(self, name=False):
        user = auth.getCurrentUser()
        response = {}
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
            try:
                channel = channels.Channel(device.address,
                        override_quota=user_data.immune())
                response['token'] = channel.token
                if channel.cached:
                    response['code'] = 304
                else:
                    response['code'] = 200
            except channels.OverQuotaError:
                response['code'] = 503
                response['token'] = 'overquota'
                response['message'] = "Server is over quota."
        else:
            response['code'] = 401
            response['message'] = 'Not logged in.'
        self.response.out.write(simplejson.dumps(response))


class MarkAsReadHandler(webapp.RequestHandler):
    def post(self, json=False):
        json = self.request.get('links')
        if json != False:
            sent_data = simplejson.loads(json)
            for link in sent_data:
                link_data = models.getLink(link)
                link_data.markRead()


class SetQuotaHandler(webapp.RequestHandler):
    def get(self):
        quota = models.getQuota()
        cur_quota = 0
        if quota.amount:
            cur_quota = quota.amount
        vars = {
                'current': cur_quota
        }
        logging.debug(quota.amount)
        path = os.path.join(os.path.dirname(__file__), 'quota.html')
        self.response.out.write(template.render(path, vars))

    def post(self):
        quota = self.request.POST['quota']
        newQuota = models.updateQuota(quota)
        self.response.out.write("Quota updated to %s channels." %
                newQuota.amount)


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
        record_value = simplejson.loads(record.value)
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
                    record.timestamp, duration='day'))
                datapoints.append(models.getStats(subscriber.datapoint,
                    record.timestamp, duration='hour'))
        for datapoint in datapoints:
            if datapoint.datapoint == 'active_users':
                try:
                    user = models.getUser(record_value['user'], False)
                except models.UserDoesNotExistError:
                    break
                if user.last_seen.date() < timestamp.now().date():
                    user.updateLastSeen()
                else:
                    break
            if datapoint.datapoint == 'quota':
                datapoint.count = models.getQuota().amount
            else:
                datapoint.increment()
            json = {'datapoint': datapoint.datapoint, 'count': datapoint.count,
                    'date': datapoint.date.strftime("%A %B %d, %Y at %H:%M"),
                    'timestamp': int(time.mktime(
                        datapoint.date.timetuple())) * 1000,
                    'duration': datapoint.duration}
            stats_json.append(json)
        db.put(datapoints)
        push = channels.Channel("stats@2cloudproject.com/Web", False)
        push.message = {"stats": stats_json}
        push.send()
        logging.debug(simplejson.dumps(stats_json))


class StatsDashboard(webapp.RequestHandler):
    def get(self):
        user = users.User('stats@2cloudproject.com')
        try:
            user_data = models.getUser(user)
        except models.UserDoesNotExistError:
            user_data = models.UserData(user=user).save()
        try:
            device = models.getDevice("%s/%s" % (user.email(), "Web"))
        except models.DeviceDoesNotExistError:
            device = models.DeviceData(user=user_data,
                    name="Web").save()
        channel = channels.Channel(device.address, override_quota=True)
        path = os.path.join(os.path.dirname(__file__), 'dashboard.html')
        daily_stats_data = models.StatsData.all().filter('duration =',
                'day').order("-date").fetch(270)
        hourly_stats_data = models.StatsData.all().filter('duration =',
                'hour').order('-date').fetch(216)
        template_values = {
                'channel_id': channel.token,
                'stats': {'hour': {}, 'day': {}}
        }
        stats = template_values['stats']
        for datapoint in daily_stats_data:
            if not datapoint.datapoint in stats['day']:
                stats['day'][datapoint.datapoint] = []
            stats['day'][datapoint.datapoint].append({
                    'name': datapoint.datapoint,
                    'date': datapoint.date.strftime("%A %B %d, %Y"),
                    'timestamp': int(time.mktime(
                        datapoint.date.timetuple()) * 1000),
                    'count': int(datapoint.count),
                    'duration': datapoint.duration
            })
        for datapoint in hourly_stats_data:
            if not (datapoint.datapoint in stats['hour']):
                stats['hour'][datapoint.datapoint] = []
            stats['hour'][datapoint.datapoint].append({
                    'name': datapoint.datapoint,
                    'date': datapoint.date.strftime("%A %B %d, %Y at %H:%M"),
                    'timestamp': int(time.mktime(
                        datapoint.date.timetuple()) * 1000),
                    'count': int(datapoint.count),
                    'duration': datapoint.duration
            })
        stats['hour'] = stats['hour'].values()
        stats['day'] = stats['day'].values()
        stats['hour'] = sorted(stats['hour'],
                key=lambda stat: stat[0]['name'])
        stats['day'] = sorted(stats['day'], key=lambda stat: stat[0]['name'])
        template_values['stats'] = stats
        self.response.out.write(template.render(path, template_values))


class StatsInit(webapp.RequestHandler):
    def get(self, duration='hour'):
        datapoints = ['registrations', 'links', 'opened_links', 'channels',
                'devices', 'connections', 'active_users', 'quota']
        for datapoint in datapoints:
            datapoint = models.getStats(datapoint, duration=duration)


class QuotaCountdown(webapp.RequestHandler):
    def get(self):
        stamp = timestamp.now()
        reset = stamp.replace(day=stamp.day + 1, hour=0, minute=0, second=0,
                microsecond=0)
        countdown = reset - stamp
        response = {}
        response['readable'] = str(countdown)
        response['seconds'] = countdown.seconds + (countdown.days * 24 * 3600)
        self.response.out.write(simplejson.dumps(response))


class PaymentNotificationHandler(webapp.RequestHandler):
    def post(self):
        user = auth.getCurrentUser()
        response = {}
        if user:
            try:
                user_data = models.getUser(user)
            except models.UserDoesNotExistError:
                user_data = models.UserData(user=user).save()
            payment_data = models.PaymentData(date=timestamp.now(),
                    user=user_data, item=self.request.get("item_id"),
                    order_number=self.request.get("order_number"),
                    status="unconfirmed")
            payment_data.save()

application = webapp.WSGIApplication([
        ('/', MainPage),
        ('/links/add', AddLinkPage),
        ('/links/mark_read', MarkAsReadHandler),
        ('/channels/connected', ConnectedPage),
        ('/channels/connected/([^/]*)', ConnectedPage),
        ('/channels/get', TokenPage),
        ('/channels/get/(.*)', TokenPage),
        ('/stats/subscribe', SubscribeHandler),
        ('/stats/dashboard', StatsDashboard),
        ('/stats/init/(.*)', StatsInit),
        ('/quota/countdown', QuotaCountdown),
        ('/quota/set', SetQuotaHandler),
        ('/_ah/prospective_search', StatsHandler),
        ('/payments/notification', PaymentNotificationHandler)
        ], debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
