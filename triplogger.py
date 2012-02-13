import sched, time, random, yaml, foursquare
from datetime import datetime, timedelta
from datetime import time as dtime
from random import *


""" A class for categorizing venue types and containing respective check-in and
    check-out times, along with the minimum time to travel from this venue to
    another. """
class Category(yaml.YAMLObject):
  yaml_tag = u'!Category'
  def __init__(self,in_start=8,in_stop=12,out_start=14,out_stop=20,
      transit_time=1):
    self.in_start = in_start
    self.in_stop = in_stop
    self.out_start = out_start
    self.out_stop = out_stop
    self.transit_time = timedelta(hours=transit_time)

""" PyYAML ignores the actual constructor unless we force it to use it. """
def category_constructor(loader, node):
  value = loader.construct_mapping(node)
  return Category(**value)

""" A class for encapsulating the Foursquare Venue ID and our check-in 
    settings. """
class Venue(yaml.YAMLObject):
  yaml_tag = u'!Venue'
  def __init__(self,category=None,id=None):
    self.category = category
    self.id = id
    self.offset = timedelta(days=0)

  """ Check-in at a random time in the specified interval. """
  def getCheckinTime(self):
    time = datetime.now()
    if time.hour > self.category.in_stop:
      # If it's too late to checkin, wait until tomorrow
      self.offset += timedelta(days=1)
      time += self.offset

    time = time.replace(hour=randint(self.category.in_start,
      self.category.in_stop),minute=randint(0,59),second=randint(0,59))

    return time

  def getCheckoutTime(self):
    time = datetime.today() + timedelta(days=1) + self.offset
    time = time.replace(hour=randint(self.category.out_start,
      self.category.out_stop),minute=randint(0,59),second=randint(0,59))

    self.offset = timedelta(days=0)

    return time


""" Force PyYAML to use the actual constructor. """
def venue_constructor(loader, node):
  value = loader.construct_mapping(node)
  return Venue(**value)


""" A class to organize check-ins and check-outs. """
class Trip(yaml.YAMLObject):
  yaml_tag = u'!Trip'
  def __init__(self,checkins=None,checkouts=None):
    self.checkins = checkins
    self.checkouts = checkouts

def trip_constructor(loader,node):
  value = loader.construct_mapping(node)
  return Trip(**value)

""" Schedule all events for our selected trip. """
def schedule_trip(trip,scheduler,api):
  previous = datetime.now() - timedelta(days=1)
  prior_venue = None

  for i in trip.checkins:
    c = i.getCheckinTime()
    if prior_venue:
      if previous + prior_venue.category.transit_time > c:
        c += prior_venue.category.transit_time

    previous = c
    prior_venue = i
    scheduler.enterabs(c,1,api.checkins.add,({'venueId': i.id},))

  if trip.checkouts:
    for i in trip.checkouts:
      c = i.getCheckoutTime()
      if prior_venue:
        if previous + prior_venue.category.transit_time > c:
          c += prior_venue.category.transit_time

      previous = c
      scheduler.enterabs(c,1,api.checkins.add,({'venueId': i.id},))

  # Compute the midnight after our last checkout
  d = previous.date() + timedelta(days=1)
  t = dtime(0)
  midnight = datetime.combine(d,t)

  # Schedule an event so the queue isn't empty until the next day
  scheduler.enterabs(midnight,1,nothing,())
  return scheduler


""" Do nothing. """
def nothing():
  return None


""" Randomly select a trip from our list of trips. """
def schedule_trips(scheduler, trips, api):
  if len(trips) == 0:
    return scheduler
  t = trips[randint(0,len(trips)-1)]
  scheduler = schedule_trip(t,scheduler,api)
  return scheduler


""" datetime doesn't provide a sleep function, so we convert timedeltas into
    seconds."""
def datetime_sleep(s):
  # sched.delay_func sometimes passes int(0) to this function for some reason
  if isinstance(s,int):
    time.sleep(float(s))
  else:
    time.sleep(s.total_seconds())


if __name__ == '__main__':
  config = open('config.yml')

  yaml.add_constructor(u'!Category',category_constructor)
  yaml.add_constructor(u'!Venue',venue_constructor)

  data = yaml.load_all(config)
  api_data = data.next()
  trip_data = data.next()

  client = foursquare.Foursquare(**api_data)

  if api_data['access_token']:
    client.set_access_token(api_data['access_token'])
  else:
    auth_url = client.oauth.auth_url()
    print 'Auth at:', auth_url

    code = raw_input('Enter code: ').strip()

    access_token = client.oauth.get_token(code)
    print 'Access token:', access_token

  s = sched.scheduler(datetime.now, datetime_sleep)

  trips = trip_data['trips']

  print trip_data

  while s.empty():
    s = schedule_trips(s,trips,client)
    for i in s.queue:
      print i
    s.run()
