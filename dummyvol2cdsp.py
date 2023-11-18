#!/usr/bin/python

# dummyvol2cdsp v0.1.0 - Forward Alsa dummy device volume to CamillaDSP
# Copyright (c) 2022 Roderick van Domburg

##############################################################################
# Many DACs report an enormous but unusable volume range. This script uses a
# cubic mapping to maximize the usable range of the volume slider. 60 dB is a
# common and appropriate range of volume control. In environments with less
# background noise, such as headphones or treated studios, you may want to
# try as high as 90 dB. Sane values would be from 50-100.
VOL_RANGE = 60

# CamillaDSP IP address
CDSP_HOST = '127.0.0.1'

# CamillaDSP port number
CDSP_PORT = 1234

# Alsa dummy device name
DUMMY_DEV = 'hw:Dummy'

# Alsa dummy mixer control name
DUMMY_CTL = 'Master'
##############################################################################
import select
import time

from alsaaudio import Mixer
from camilladsp import CamillaConnection
from math import log10, exp, log
from pathlib import Path

mixer = Mixer(device=DUMMY_DEV, control=DUMMY_CTL)
cdsp = CamillaConnection(CDSP_HOST, CDSP_PORT)

def lin_vol_curve(perc: int, dynamic_range: float= 60.0) -> float:
    '''
    Generates from a percentage a dBA, based on a curve with a dynamic_range.
    Curve calculations coming from: https://www.dr-lex.be/info-stuff/volumecontrols.html

    @perc (int) : linair value between 0-100
    @dynamic_range (float) : dynamic range of the curve
    return (float): Value in dBA
    '''
    x = perc/100.0
    y = pow(10, dynamic_range/20)
    a = 1/y
    b = log(y)
    y=a*exp(b*(x))
    if x < .1:
        y = x*10*a*exp(0.1*b)
    if y == 0:
        y = 0.000001
    return 20* log10(y)

def store_volume(volume_db: float, mute: int=0):
   _volume_state_file = Path('/var/lib/cdsp/camilladsp_volume_state')
   try:
        _volume_state_file.write_text('{} {}'.format(volume_db, mute))
   except FileNotFoundError as e:
        print('Couldn\'t create state file "%s", prob basedir doesn\'t exists.', _volume_state_file)
        pass
   except PermissionError as e:
        print('Couldn\'t write state to "%s", prob incorrect owner rights of dir.', _volume_state_file)
        pass
    
def sync_volume():         
   # assume that channel volume is equal                                                                                                                                                                                                                                                  
   alsavol = mixer.getvolume()[0]                                                                                                                                                                                                                                                         
   dbvol = lin_vol_curve(alsavol, VOL_RANGE)
   mute = 1 if abs(dbvol) >= VOL_RANGE else 0   
   store_volume(dbvol, mute)

   print('alsa=%d%% dbvol=%.1f dB mute=%s' % (alsavol, dbvol, mute))

   try:                
       if not cdsp.is_connected():
           cdsp.connect()
            
       cdsp.set_volume(dbvol)        
       if mute == 1 and not cdsp.get_mute():
           cdsp.set_mute(True)
       elif cdsp.get_mute():
           cdsp.set_mute(False)

   except Exception as err:                                                                                                                                                                                                                                                           
       print('setting cdsp volume failed: {0}'.format(err))
       pass

if __name__ == '__main__':
    # synchronize on initial startup
    sync_volume()
    
    # handle volume changes
    poll = select.poll()
    descriptors = mixer.polldescriptors()
    poll.register(descriptors[0][0])    
    while True:
        poll.poll()
        mixer.handleevents()
        sync_volume()
