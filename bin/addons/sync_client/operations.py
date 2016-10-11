# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv, fields
import logging, traceback, sys

# Operational events are things that happen while Unifield is running
# that we would like to have recorded so that we can investigate/summarize
# via queries on non-production instances. Once written by Unifield
# in response to something happening, they are read-only. They can be
# inspected using the Search view, or exported via SQL to another
# system for processing.
class operations_event(osv.osv):

    _name = 'operations.event'
    _columns = {
        'when': fields.datetime('When', readonly=True, select=True, help="When the event happened."),
        'kind': fields.char('Kind', readonly=True, size=64, required=True, help="What kind of event it was."),
        'data': fields.text('Data', readonly=True, help="The data associated with the event.")
    }

    _defaults = {
        'when': lambda self,cr,uid,c: fields.datetime.now()
    }

    _logger = logging.getLogger('operations.event')

    # returns the id of the new event
    def create_from_traceback(self, cr, uid, exc_info, context=None):
        data = {
            'kind': 'traceback',
            'data': ''.join(traceback.format_exception(*exc_info))
        }
        id = self.create(cr, uid, data, context=context)
        return id

    def bang(self, cr, uid, ids=None, context=None):
        try:
            raise ValueError("bang!")
        except Exception as e:
            self.create_from_traceback(cr, uid, sys.exc_info(), context=None)
        return 1
    
operations_event()
