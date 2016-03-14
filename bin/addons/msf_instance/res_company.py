#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
from tools.translate import _
import logging
import tools
from os import path

class res_company(osv.osv):
    _name = 'res.company'
    _inherit = 'res.company'
    
    def init(self, cr):
        """
            Create a instance for yml test
        """
        if hasattr(super(res_company, self), 'init'):
            super(res_company, self).init(cr)

        mod_obj = self.pool.get('ir.module.module')
        demo = False
        mod_id = mod_obj.search(cr, 1, [('name', '=', 'msf_instance')])
        if mod_id:
            demo = mod_obj.read(cr, 1, mod_id, ['demo'])[0]['demo']
        if demo:
            current_module = 'msf_instance'
            file_to_load = '%s/data/instance_data.xml' % (current_module, )

            logging.getLogger('init').info('HOOK: module msf_instance: loading %s' % file_to_load)
            file = tools.file_open(file_to_load)
            tools.convert_xml_import(cr, current_module, file, {}, mode='init', noupdate=False)

    _columns = {
        'instance_id': fields.many2one('msf.instance', string="Proprietary Instance", 
            help="Representation of the current instance"),
        'second_time': fields.boolean('Config. Wizard launched for the second time'),
        'company_second_time': fields.boolean('Company Config. Wizard launched for the second time'),
    }
    
    _defaults = {
        'second_time': lambda *a: False,
        'company_second_time': lambda *a: False,
    }

    def _refresh_objects(self, cr, uid, object_name, old_instance_id, new_instance_id, context=None):
        object_ids = self.pool.get(object_name).search(cr,
                                                       uid,
                                                       [('instance_id', '=', old_instance_id)],
                                                       context=context)
        self.pool.get(object_name).write(cr,
                                         uid,
                                         object_ids,
                                         {'instance_id': new_instance_id},
                                         context=context)
        return
    
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        Erase some unused data copied from the original object, which sometime could become dangerous, as in UF-1631/1632, 
        when duplicating a new partner (by button duplicate), or company, it creates duplicated currencies
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}
        fields_to_reset = ['currency_ids'] # reset this value, otherwise the content of the field triggers the creation of a new company
        to_del = []
        for ftr in fields_to_reset:
            if ftr not in default:
                to_del.append(ftr)
        res = super(res_company, self).copy_data(cr, uid, id, default=default, context=context)
        for ftd in to_del:
            if ftd in res:
                del(res[ftd])
        return res
    
    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        if 'currency_id' in vals:
            for company in self.browse(cr, uid, ids, context=context):
                sale = self.pool.get('product.pricelist').search(cr,uid,[('currency_id','=',vals['currency_id']), ('type','=','sale')])
                purchase = self.pool.get('product.pricelist').search(cr,uid,[('currency_id','=',vals['currency_id']), ('type','=','purchase')])
                tmp_vals = {}
                if sale:
                    tmp_vals['property_product_pricelist'] = sale[0]
                if purchase:
                    tmp_vals['property_product_pricelist_purchase'] = purchase[0]
                if tmp_vals:
                    self.pool.get('res.partner').write(cr, uid, [company.partner_id.id], tmp_vals, context=context)

        instance_obj = self.pool.get('msf.instance')
        if 'instance_id' in vals:
            # only one company (unicity)
            if len(ids) != 1:
                raise osv.except_osv(_('Error'), _("Only one company per instance!") or '')
            company = self.browse(cr, uid, ids[0], context=context)
            instance_data = {
                'instance': cr.dbname,
                'state': 'active',
                'instance_identifier': self.pool.get("sync.client.entity").get_entity(cr, uid, context=context).identifier,
            }
            if not company.instance_id:
                # An instance was not set; add DB name and activate it
                instance_obj.write(cr, uid, [vals['instance_id']], instance_data, context=context)
            elif company.instance_id.id != vals.get('instance_id'):
                # An instance was already set
                old_instance_id = company.instance_id.id
                # Deactivate the instance
                instance_obj.write(cr, uid, [old_instance_id], {'state': 'inactive', 'instance_identifier': False}, context=context)
                # add DB name and activate it
                instance_obj.write(cr, uid, [vals['instance_id']], instance_data, context=context)
                # refresh all objects
                for object in ['account.analytic.journal', 'account.journal', 'account.analytic.line', 'account.move', 'account.move.line', 'account.bank.statement']:
                    self._refresh_objects(cr, uid, object, old_instance_id, vals['instance_id'], context=context)
        return super(res_company, self).write(cr, uid, ids, vals, context=context)
                
res_company()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
