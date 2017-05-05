# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 TeMPO Consulting, MSF
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

from osv import fields
from osv import osv

from tools.translate import _


class po_automation_config(osv.osv):
    _name = 'po.automation.config'

    _columns = {
        'name': fields.selection(
            selection=[
                ('yes', 'Yes'),
                ('no', 'No'),
            ],
            string='Run scheduler automatically ?',
            required=True,
        ),
    }

    _defaults = {
        'name': 'yes',
    }

    def create(self, cr, uid, vals, context=None):
        """
        Check that there is only one PO Automation configuration record
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param vals: Values for the new created record
        :param context: Context of the call
        :return: ID of the new po.automation.config record
        """
        if context is None:
            context = {}

        if self.search(cr, uid, [], limit=1, context=context):
            raise osv.except_osv(
                _('Error'),
                _('It is forbidden to have more than one PO Automation configuration record'),
            )

        return super(po_automation_config, self).create(cr, uid, vals, context=context)

    def save(self, cr, uid, ids, context=None):
        """
        Just save the value on the PO Automation configuration record
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of po.automation.config to save
        :param context: Context of the call
        :return: True
        """
        return True

    def get_po_automation(self, cr, uid, context=None):
        """
        Return True if the configuration of the PO Automation is 'Yes', else, return False
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls this method
        :param context: Context of the call
        :return: True or False
        """
        if context is None:
            context = {}

        conf_ids = self.search(cr, uid, [], limit=1, context=context)
        for conf in self.browse(cr, uid, conf_ids, context=context):
            if conf.name == 'no':
                return False

        return True

po_automation_config()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
