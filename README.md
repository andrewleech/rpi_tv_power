rpi_tv_power
============

Using a raspberry pi to turn a tv on/off automatically with media centre (mythtv) usage


Description
============

I'm using mythtv as my media center in the lounge room, connected to a Sony TV. 
This TV has a feature where, when it's in computer input mode, it will act like a monitor and turn off when the computer puts the monitor into standby.
This means I can have the media centre set up to put the tv into standby when it's idle, and then turn on instantly at the press of any remote button. Seeing as my media centre is the only thing we ever use the tv for, we never need to pick up the tv remote, we can have just the one remote for everything (the media centre).

Now for some stupid reason this only works with vga input, and will not work with hdmi. When I finally decided I really wanted hdmi for the image quality I went hunting for a way to replicate this.

Enter hdmi cec control channel (aka bravia sync on sony or viera link on panasonic and similar on everything else).
With this you can look at what devices are plugged into hdmi, query/change what input the tv is set to, and most importantly tell the tv to turn on or off.
Unfortunately no pc graphics cards come with support for this (why not intel/ati/nvidia???). You can buy a USB cec adapter though, but it costs ~$60. Alternately, the rarsberry pi comes with it built in surprisingly enough, and it's cheap. So I bought one.

Basic system is have the mythttv media centre plugged into one of the hdmi inputs on the tv,
Rarsberry Pi is plugged into another hdmi input.
Both media centre and pi are on the same network

Media centre has a server service running on it that will monitor usage/idle.
Pi will have client service running that queries server for idle status, and turn the tv on/off as required.

Seems simple enough.

I've gone and overcomplicated it slightly as I was running into severe reliability issues whenever I tried to use either xscreensaver or dpms to monitor idle timeouts. Sometimes they would just get disabled and never time out. Other times they would stop responding ot one or the other my our remotes (I've got two separate remotes that both do the same thing, but one acts as a keyboard, the other as lirc) and the tv wouldn't turn on from the remote. 
So, I've made my own idle monitor. It checks for both lirc events, keypress events (thanks to an external keylogging style script, pyxhook) and it monitors the status output from mythfrontend to know if there's a video playing. I haven't yet extended it to monitor xbmc, although it's on the todo list.

On the pi end, I also monitor whether the tv is set to the myth box, if for some reason it's been changed to watch live tv, the script won't turn the tv off.

At the top of each script there's a couple of variables; hopefully self explanitary.
They can be run on demand, as a background job, in a screen or at startup whatever way suits the linux distro in use.

Contact me if you need any assistance getting it going!

Cheers,
Andrew Leech

www.alelec.net
https://github.com/coronafire/rpi_tv_power
