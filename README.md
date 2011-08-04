## 2cloud App Engine Server

### About

2cloud is a free, decentralised, open source project to try and make sharing 
content between browsers and devices as seamless and effortless as possible. An 
up-to-date list of devices and browsers supported by the project is available at 
http://www.2cloudproject.com/clients

This is the App Engine software that powers our public server at 
https://2cloudapp.appspot.com. We provide it here as a reference for implementing 
your own server software for the project and as a plug and play package for users 
who want to host their own servers, but don't necessarily want to write their own 
server.

### Installation Instructions

We tried to make installation as streamlined as possible. You just need to 
download the source (use git, or the download button) and change the identifier 
in app.yaml. Then use the 
[http://code.google.com/appengine/downloads.html#Google_App_Engine_SDK_for_Python](App 
Engine SDK) to sync it just like you 
[http://code.google.com/appengine/docs/python/gettingstarted/uploading.html](normally 
would).

### Where to Get Help

We try to maintain a presence with our users. To wit, we have:

* A Tender support site (the best way to get help with "it's not working"): http://help.2cloudproject.com
* An announcement mailing list (the best way to stay up-to-date on downtime and changes): http://groups.google.com/group/2cloud-announce
* A discussion mailing list (the best way to talk to other users and the team): http://groups.google.com/group/2cloud
* A development mailing list (the best way to stay on top of API changes): http://groups.google.com/groups/2cloud-dev
* A beta mailing list (if you want to help test buggy software): http://groups.google.com/group/2cloud-beta
* A Twitter account (the best way to stay on top of new releases and other updates): http://www.twitter.com/2cloudproject
* A Facebook page (the second best way to stay on top of new releases and other updates): http://www.facebook.com/2cloud
* A website (for a bunch of other links and information): http://www.2cloudproject.com
* A blog (for lengthier updates and explanations): http://blog.2cloudproject.com
* A Github account (where all our source code and issues reside): https://www.github.com/2cloud

If you don't use _any_ of those... you're kind of out of luck.

### Contribution Guidelines

The quickest, easiest, and most assured way to contribute is to be a beta tester.
Simply join the [http://groups.google.com/group/2cloud-beta](mailing list) and 
wait for a new beta to be released. Try and break it. Submit feedback. Wash, 
rinse, repeat.

If you're interested in contributing code, we use different guidelines for each 
part of our app. This is driven by necessity; you can't use PEP-8 on Java, for 
example. Our App Engine guidelines are simple:

* If possible, have unit tests written for what you're patching
* Explain clearly in your pull request what you're patching and why
* Make sure your code follows the style laid out in PEP-8

That's pretty much it. We're laid back. The best way to figure out what's on our 
to-do list is to look at the [https://www.github.com/2cloud/AppEngine/issues](issue 
tracker) or ask on the [http://groups.google.com/group/2cloud-dev](dev mailing list). 
Whatever you work on should be something _you_ want to see implemented, though.

### Contributors

2cloud is an open source application. It is technically "owned" by [Second Bit LLC](http://www.secondbit.org), 
but all that really means is they take care of the mundane administrative and 
financial stuff. The team behind 2cloud is separate from the Second Bit team 
(despite some overlap). The 2cloud team is as follows:

* Paddy Foran - Lead Developer - [@paddyforan](http://www.twitter.com/paddyforan) - http://www.paddyforan.com/
* Dylan Staley - UI/UX Lead - [@dstaley](http://www.twitter.com/dstaley) - http://www.dstaley.me
* Tino Galizio - Project Manager - [@tinogalizio](http://www.twitter.com/tinogalizio) - http://www.secondbit.org/team/tino

They're pretty friendly. Please do get in touch!

### Credits and Alternatives

One of the great parts about being an open source project is how often we get to 
stand on the shoulders of giants. Without these people and projects, we couldn't 
do what we do.

* blog.notdot.net (basis of stats system)
* docs.python.org (basis of timestamp.py)
* jQuery (Stats dashboard)
* Chrome to Phone (Inspiration)

There are some alternatives to 2cloud out there, and we encourage you to try them 
out. Use what works best for you. You can find an up-to-date list on 
[http://links.2cloudproject.com/competition](our website).
