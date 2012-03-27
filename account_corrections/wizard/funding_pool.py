#!/usr/bin/env python
#-*- encoding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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

from osv import osv
from osv import fields
import time
from tools.translate import _


class wizard_costcenter_distribution(osv.osv_memory):
    _inherit = 'wizard.costcenter.distribution'

    _columns = {
        'date': fields.date(string="Date", help="This date is taken from analytic distribution corrections"),
        'state': fields.selection([('normal', 'Normal'), ('correction', 'Correction')], string="State"),
    }

    _defaults = {
        'state': lambda *a: 'normal',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def button_cancel(self, cr, uid, ids, context={}):
        """
        Close wizard and return on another wizard if 'from' and 'wiz_id' are in context
        """
        # Some verifications
        if not context:
            context = {}
        if 'from' in context and 'wiz_id' in context:
            wizard_name = context.get('from')
            wizard_id = context.get('wiz_id')
            return {
                'type': 'ir.actions.act_window',
                'res_model': wizard_name,
                'target': 'new',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': wizard_id,
                'context': context,
            }
        return super(wizard_costcenter_distribution, self).button_cancel(cr, uid, ids, context=context)

    def button_next_step(self, cr, uid, ids, context={}):
        """
        Add date to next wizard then launch it
        """
        # Some verifications
        if not context:
            context = {}
        current = 'cost_center'
        res = super(wizard_costcenter_distribution, self).button_next_step(cr, uid, ids, context=context)
        if 'from' in context and 'wiz_id' in context:
            if 'res_model' in res and 'res_id' in res:
                if 'wizard_ids' in context and current in context.get('wizard_ids'):
                    current_distribution = self.pool.get(self._name).browse(cr, uid, context.get('wizard_ids').get(current), context=context)
                    wiz_obj = self.pool.get(res.get('res_model')).write(cr, uid, res.get('res_id'), {'state': 'correction', 'date': current_distribution.date})
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': res.get('res_model'),
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'res_id': res.get('res_id'),
                        'context': context
                        }
        return res

wizard_costcenter_distribution()

class wizard_fundingpool_distribution(osv.osv_memory):
    _inherit = 'wizard.fundingpool.distribution'

    _columns = {
        'date': fields.date(string="Date", help="This date is taken from analytic distribution corrections"),
        'state': fields.selection([('normal', 'Normal'), ('correction', 'Correction')], string="State"),
    }

    _defaults = {
        'state': lambda *a: 'normal',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def return_on_wizard(self, cr, uid, wiz_name=None, wiz_id=None, context={}):
        """
        Return a wizard which name is wiz_name and id is wiz_id
        """
        # Some verifications
        if not context:
            context = {}
        if not wiz_name and not wiz_id:
            raise osv.except_osv(_('Error'), _('No name view or no id given!'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': wiz_name,
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': wiz_id,
            'context': context,
        }

    def button_cancel(self, cr, uid, ids, context={}):
        """
        Close wizard and return on another wizard if 'from' and 'wiz_id' are in context
        """
        # Some verifications
        if not context:
            context = {}
        # Return to the initial wizard if 'from' in context
        if 'from' in context and 'wiz_id' in context:
            wizard_name = context.get('from')
            wizard_id = context.get('wiz_id')
            # return to wizard named "wizard_name"
            return self.return_on_wizard(cr, uid, wizard_name, wizard_id, context=context)
        # else, return normal behaviour
        return super(wizard_fundingpool_distribution, self).button_cancel(cr, uid, ids, context=context)

    def button_next_step(self, cr, uid, ids, context={}):
        """
        Add date to next wizard then launch it
        """
        # Some verifications
        if not context:
            context = {}
        current = 'funding_pool'
        res = super(wizard_fundingpool_distribution, self).button_next_step(cr, uid, ids, context=context)
        if 'from' in context and 'wiz_id' in context:
            if 'res_model' in res and 'res_id' in res:
                if 'wizard_ids' in context and current in context.get('wizard_ids'):
                    current_distribution = self.pool.get(self._name).browse(cr, uid, context.get('wizard_ids').get(current), context=context)
                    wiz_obj = self.pool.get(res.get('res_model')).write(cr, uid, res.get('res_id'), {'state': 'correction', 'date': current_distribution.date})
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': res.get('res_model'),
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'res_id': res.get('res_id'),
                        'context': context
                        }
        return res

    def store_distribution(self, cr, uid, wizard_id, date=False, source_date=False, context={}):
        """
        Give source date to the initial method
        """
        if not context:
            context = {}
        current = 'funding_pool'
        if 'wizard_ids' in context and current in context.get('wizard_ids'):
            current_distribution = self.pool.get(self._name).browse(cr, uid, context.get('wizard_ids').get(current), context=context)
            date = date or current_distribution.date or False
            source_date = source_date or current_distribution.date or False
        return super(wizard_fundingpool_distribution, self).store_distribution(cr, uid, wizard_id, date, source_date, context=context)

wizard_fundingpool_distribution()

class wizard_free1_distribution(osv.osv_memory):
    _inherit = 'wizard.free1.distribution'

    _columns = {
        'date': fields.date(string="Date", help="This date is taken from analytic distribution corrections"),
        'state': fields.selection([('normal', 'Normal'), ('correction', 'Correction')], string="State"),
    }

    _defaults = {
        'state': lambda *a: 'normal',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def return_on_wizard(self, cr, uid, wiz_name=None, wiz_id=None, context={}):
        """
        Return a wizard which name is wiz_name and id is wiz_id
        """
        # Some verifications
        if not context:
            context = {}
        if not wiz_name and not wiz_id:
            raise osv.except_osv(_('Error'), _('No name view or no id given!'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': wiz_name,
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': wiz_id,
            'context': context,
        }

    def button_cancel(self, cr, uid, ids, context={}):
        """
        Close wizard and return on another wizard if 'from' and 'wiz_id' are in context
        """
        # Some verifications
        if not context:
            context = {}
        # Return to the initial wizard if 'from' in context
        if 'from' in context and 'wiz_id' in context:
            wizard_name = context.get('from')
            wizard_id = context.get('wiz_id')
            # return to wizard named "wizard_name"
            return self.return_on_wizard(cr, uid, wizard_name, wizard_id, context=context)
        # else, return normal behaviour
        return super(wizard_free1_distribution, self).button_cancel(cr, uid, ids, context=context)

    def button_next_step(self, cr, uid, ids, context={}):
        """
        Add date to next wizard then launch it
        """
        # Some verifications
        if not context:
            context = {}
        current = 'free_1'
        res = super(wizard_free1_distribution, self).button_next_step(cr, uid, ids, context=context)
        if 'from' in context and 'wiz_id' in context:
            if 'res_model' in res and 'res_id' in res:
                if 'wizard_ids' in context and current in context.get('wizard_ids'):
                    current_distribution = self.pool.get(self._name).browse(cr, uid, context.get('wizard_ids').get(current), context=context)
                    wiz_obj = self.pool.get(res.get('res_model')).write(cr, uid, res.get('res_id'), {'state': 'correction', 'date': current_distribution.date})
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': res.get('res_model'),
                        'view_type': 'form',
                        'view_mode': 'form',
                        'target': 'new',
                        'res_id': res.get('res_id'),
                        'context': context
                        }
        return res

    def store_distribution(self, cr, uid, wizard_id, date=False, source_date=False, context={}):
        """
        Give source date to the initial method
        """
        if not context:
            context = {}
        current = 'free_1'
        if 'wizard_ids' in context and current in context.get('wizard_ids'):
            current_distribution = self.pool.get(self._name).browse(cr, uid, context.get('wizard_ids').get(current), context=context)
            date = date or current_distribution.date or False
            source_date = source_date or current_distribution.date or False
        return super(wizard_free1_distribution, self).store_distribution(cr, uid, wizard_id, date, source_date, context=context)

wizard_free1_distribution()

class wizard_free2_distribution(osv.osv_memory):
    _inherit = 'wizard.free2.distribution'

    _columns = {
        'date': fields.date(string="Date", help="This date is taken from analytic distribution corrections"),
        'state': fields.selection([('normal', 'Normal'), ('correction', 'Correction')], string="State"),
    }

    _defaults = {
        'state': lambda *a: 'normal',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def return_on_wizard(self, cr, uid, wiz_name=None, wiz_id=None, context={}):
        """
        Return a wizard which name is wiz_name and id is wiz_id
        """
        # Some verifications
        if not context:
            context = {}
        if not wiz_name and not wiz_id:
            raise osv.except_osv(_('Error'), _('No name view or no id given!'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': wiz_name,
            'target': 'new',
            'view_mode': 'form,tree',
            'view_type': 'form',
            'res_id': wiz_id,
            'context': context,
        }

    def button_cancel(self, cr, uid, ids, context={}):
        """
        Close wizard and return on another wizard if 'from' and 'wiz_id' are in context
        """
        # Some verifications
        if not context:
            context = {}
        if 'from' in context and 'wiz_id' in context:
            wizard_name = context.get('from')
            wizard_id = context.get('wiz_id')
            return {
                'type': 'ir.actions.act_window',
                'res_model': wizard_name,
                'target': 'new',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': wizard_id,
                'context': context,
            }
        return super(wizard_free2_distribution, self).button_cancel(cr, uid, ids, context=context)

    def store_distribution(self, cr, uid, wizard_id, date=False, source_date=False, context={}):
        """
        Give source date to the initial method
        """
        if not context:
            context = {}
        current = 'free_2'
        if 'wizard_ids' in context and current in context.get('wizard_ids'):
            current_distribution = self.pool.get(self._name).browse(cr, uid, context.get('wizard_ids').get(current), context=context)
            date = date or current_distribution.date or False
            source_date = source_date or current_distribution.date or False
        return super(wizard_free2_distribution, self).store_distribution(cr, uid, wizard_id, date, source_date, context=context)

wizard_free2_distribution()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
