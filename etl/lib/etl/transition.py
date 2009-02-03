# -*- encoding: utf-8 -*-
##############################################################################
#
#    ETL system- Extract Transfer Load system
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
""" ETL Process.

    The class for ETL transition.

"""
import signal
import logger
class transition(signal.signal):
    """
       Base class of ETL transition.
    """
    

    def action_start(self,key,signal_data={},data={}):
        self.status='start'
        self.logger.notifyChannel("transition", logger.LOG_INFO, 
                     'the '+str(self)+' is start now...')
        return True 

    def action_pause(self,key,signal_data={},data={}):
        self.status='pause'
        self.logger.notifyChannel("transition", logger.LOG_INFO, 
                     'the '+str(self)+' is pause now...')
        return True 

    def action_stop(self,key,signal_data={},data={}):
        self.status='stop'
        self.logger.notifyChannel("transition", logger.LOG_INFO, 
                     'the '+str(self)+' is stop now...')
        return True    

    def __str__(self):
        return str(self.source)+' to '+str(self.destination)

    def __init__(self, source, destination, channel_source='main', channel_destination='main', type='data'):
        super(transition, self).__init__() 
        self.type = type
        self.source = source
        self.destination = destination
        self.channel_source = channel_source
        self.channel_destination = channel_destination
        self.destination.trans_in.append((channel_destination,self))
        self.source.trans_out.append((channel_source,self))
        self.status='open' # open,start,pause,stop,close 
                           # open : active, start : in running, pause : pause, stop: stop, close : inactive

        self.logger = logger.logger()
        self.signal_connect(self,'start',self.action_start)
        self.signal_connect(self,'pause',self.action_pause)
        self.signal_connect(self,'stop',self.action_stop)







