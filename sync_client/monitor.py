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
from datetime import datetime


## msf_III.3_Monitor_object
class sync_monitor(osv.osv):
    _name = "sync.monitor"

    _field_status = lambda *a,**o: fields.selection([('ok','Ok'),('null','/'),('in-progress','In Progress...'),('failed','Failed')],*a,**o)

    _columns = {
        #TODO: auto increment
        'sequence' : fields.char("Sequence", size=64, readonly=True, required=True),
        'start' : fields.datetime("Start Date", readonly=True, required=True),
        'end' : fields.datetime("End Date", readonly=True),
        'data_pull' : _field_status("Data Pull", readonly=True),
        'msg_pull' : _field_status("Msg Pull", readonly=True),
        'data_push' : _field_status("Data Push", readonly=True),
        'msg_push' : _field_status("Msg Push", readonly=True),
        'status' : _field_status("Status", readonly=True),
        'error' : fields.text("Error message", readonly=True),
    }

    def _get_default_sequence(self, cr, uid, context=None):
        return self.pool.get('ir.sequence').get(cr, uid, 'sync.monitor')
        
    _defaults = {
        'start' : lambda *a : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'sequence' : _get_default_sequence,
    }

    #must be sequence!
    _order = "sequence desc"

sync_monitor()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

