from google.appengine.api import users, oauth

def getCurrentUser():
  user = False
  try:
    user = oauth.get_current_user()
  except:
    user = users.get_current_user()
