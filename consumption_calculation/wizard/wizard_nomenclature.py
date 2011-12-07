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
        'nomen_manda_0': fields.many2one('wizard_consumption.nomenclature.line', 'N0'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'N1'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'N2'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'N3'),
    }

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context=None):
        if context is None:
            context = {}
        prod = self.pool.get('product.product')
        return prod.onChangeSearchNomenclature(cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, context)
wizard_consumption_nomenclature()

class wizard_consumption_nomenclature_nome(osv.osv_memory):
    _name = 'wizard_consumption.nomenclature.line'
    _inherit = 'product.nomenclature'

    def name_get(self, cr, uid, ids, *a, **b):
        res = []
        print uid, ids, a, b
        for nom in self.read(cr, uid, ids, ['name', 'number_of_products']):
            res.append((nom['id'],'%s (%s)'%(nom['name'], nom['number_of_products'])))
        print res
        return res

    def search(self, cr, *a, **b):
        a = super(wizard_consumption_nomenclature_nome, self).search(cr, *a, **b)
        print a
        return a
    _columns = {

    }
wizard_consumption_nomenclature_nome()
