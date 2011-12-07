# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

class wizard_consumption_nomenclature(osv.osv_memory):
    _name ='wizard_consumption.nomenclature'
    _table = 'wizard_consumption_nomenclature'

    _columns = {
        'rac_id': fields.many2one('real.average.consumption', 'RAC'),
        'nomen_manda_0': fields.many2one('wizard_consumption.nomenclature.line', 'Main Type'),
        'nomen_manda_1': fields.many2one('wizard_consumption.nomenclature.line', 'Group'),
        'nomen_manda_2': fields.many2one('wizard_consumption.nomenclature.line', 'Family'),
        'nomen_manda_3': fields.many2one('wizard_consumption.nomenclature.line', 'Root'),
        
#        'nomen_sub_0': fields.many2one('wizard_consumption.nomenclature.line', 'Sub Class 1'),
#        'nomen_sub_1': fields.many2one('wizard_consumption.nomenclature.line', 'Sub Class 2'),
#        'nomen_sub_2': fields.many2one('wizard_consumption.nomenclature.line', 'Sub Class 3'),
#        'nomen_sub_3': fields.many2one('wizard_consumption.nomenclature.line', 'Sub Class 4'),
#        'nomen_sub_4': fields.many2one('wizard_consumption.nomenclature.line', 'Sub Class 5'),
#        'nomen_sub_5': fields.many2one('wizard_consumption.nomenclature.line', 'Sub Class 6'),
    }

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None):
        if context is None:
            context = {}
        prod = self.pool.get('product.product')
        return prod.onChangeSearchNomenclature(cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context)

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        line = self.pool.get('wizard_consumption.nomenclature.line')
        ret = super(wizard_consumption_nomenclature, self).fields_view_get( cr, uid, view_id, view_type, context, toolbar, submenu)
        if context.get('rac_id'):
            obj = self.browse(cr, uid, context['rac_id'])
            for x in [0, 1, 2]:
                if obj['nomen_manda_%s'%(x,)]:
                    dom = [('parent_id', '=', obj['nomen_manda_%s'%(x,)].id), ('level', '=', x+1)]
                    ret['fields']['nomen_manda_%s'%(x+1,)]['selection'] = [(False, '')]+line._name_search(cr, uid, '', dom, context={}, limit=None, name_get_uid=1)
        return ret

    def set_nomenclature(self, cr, uid, ids, context={}):
        nom = self.browse(cr, uid, ids[0])
        rac = self.pool.get('real.average.consumption')
        write = False
        for f in ['nomen_manda_3', 'nomen_manda_2', 'nomen_manda_1', 'nomen_manda_0']:
            if nom[f]:
                rac.write(cr, uid, nom.rac_id.id, {'nomen_id': nom[f].id})
                write = True
                break
        if not write:
            rac.write(cr, uid, nom.rac_id.id, {'nomen_id': False})

        return {'type': 'ir.actions.act_window_close'}

wizard_consumption_nomenclature()

class wizard_consumption_nomenclature_nome(osv.osv):
    _name = 'wizard_consumption.nomenclature.line'
    _inherit = 'product.nomenclature'
    _table = 'product_nomenclature'

    def name_get(self, cr, uid, ids, *a, **b):
        res = []
        for nom in self.read(cr, uid, ids, ['name', 'number_of_products']):
            res.append((nom['id'],'%s (%s)'%(nom['name'], nom['number_of_products'])))
        return res

    _columns = {

    }
wizard_consumption_nomenclature_nome()
