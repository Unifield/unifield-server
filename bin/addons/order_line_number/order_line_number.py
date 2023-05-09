# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
import time


class sale_order(osv.osv):

    _inherit = 'sale.order'
    _description = 'Sales Order'
    _columns = {'sequence_id': fields.many2one('ir.sequence', 'Lines Sequence', help="This field contains the information related to the numbering of the lines of this order.", required=True, ondelete='cascade'),
                }

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new order
        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of record ids to be process
        @param context: context arguments, like lang, time zone
        @return: return a result
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Sale Order'
        code = 'sale.order'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)

    def create(self, cr, uid, vals, context=None):
        '''
        create from sale_order
        create the sequence for the numbering of the lines
        '''
        if context is None:
            context = {}

        if not context.get('keepClientOrder') or not context.get('keepDateAndDistrib') or not vals.get('sequence_id'):
            vals.update({'sequence_id': self.create_sequence(cr, uid, vals, context)})

        return super(sale_order, self).create(cr, uid, vals, context)

    def reorder_line_numbering(self, cr, uid, ids, context=None):
        '''
        test function
        '''
        # objects
        tools_obj = self.pool.get('sequence.tools')
        tools_obj.reorder_sequence_number(cr, uid, 'sale.order', 'sequence_id', 'sale.order.line', 'order_id', ids, 'line_number', context=context)
        return True

    def allow_resequencing(self, cr, uid, so_browse, context=None):
        '''
        allow resequencing criteria
        '''
        if so_browse.state == 'draft' and not so_browse.client_order_ref:
            return True
        return False

sale_order()


class sale_order_line(osv.osv):
    '''
    override of sale_order_line class
    '''
    _inherit = 'sale.order.line'
    _description = 'Sales Order Line'
    _columns = {'line_number': fields.integer(string='Line', required=True),
                }
    _order = 'order_id desc, line_number, id'

    def create(self, cr, uid, vals, context=None):
        '''
        _inherit = 'sale.order.line'
        add the corresponding line number
        '''
        # objects
        so_obj = self.pool.get('sale.order')
        seq_pool = self.pool.get('ir.sequence')

        # gather the line number from the sale order sequence if not specified in vals
        # either line_number is not specified or set to False from copy, we need a new value
        if vals.get('order_id', False):
            if not vals.get('line_number', False):
                # get max line number of all sol of the same order:
                cr.execute('''
                    select order_id, max(line_number)
                    from sale_order_line
                    where order_id = %s
                    group by order_id
                ''', (vals['order_id'],))
                res = cr.fetchone()
                # new number needed - gather the line number from the sequence
                sequence_id = so_obj.read(cr, uid, [vals['order_id']], ['sequence_id'], context=context)[0]['sequence_id'][0]
                line = seq_pool.get_id(cr, uid, sequence_id, code_or_id='id', context=context)
                while line and res and int(line) <= res[1]:
                    line = seq_pool.get_id(cr, uid, sequence_id, code_or_id='id', context=context)
                vals.update({'line_number': line})

        # create the new sale order line
        result = super(sale_order_line, self).create(cr, uid, vals, context=context)
        return result

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        if the line_number is not in the default, we set it to False
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}

        # we set line_number, so it will not be copied in copy_data - keepLineNumber - the original Line Number will be kept
        if 'line_number' not in default and not context.get('keepLineNumber', False):
            default.update({'line_number': False})
        return super(sale_order_line, self).copy_data(cr, uid, id, default, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        check the numbering on deletion
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        tools_obj = self.pool.get('sequence.tools')

        if not context.get('skipResequencing', False):
            # re sequencing only happen if field order is draft and not synchronized (PUSH flow) (behavior 1)
            draft_not_synchronized_ids = self.allow_resequencing(cr, uid, ids, context=context)
            tools_obj.reorder_sequence_number_from_unlink(cr, uid, draft_not_synchronized_ids, 'sale.order', 'sequence_id', 'sale.order.line', 'order_id', 'line_number', context=context)

        return super(sale_order_line, self).unlink(cr, uid, ids, context=context)

    def allow_resequencing(self, cr, uid, ids, context=None):
        '''
        define if a resequencing has to be performed or not

        return the list of ids for which resequencing will can be performed

        linked to Fo + Fo draft + Fo not sync
        '''
        # objects
        so_obj = self.pool.get('sale.order')

        resequencing_ids = [x.id for x in self.browse(cr, uid, ids, context=context) if x.order_id and so_obj.allow_resequencing(cr, uid, x.order_id, context=context)]
        return resequencing_ids

sale_order_line()


class purchase_order(osv.osv):

    _inherit = 'purchase.order'
    _description = 'Purchase Order'
    _columns = {'sequence_id': fields.many2one('ir.sequence', 'Lines Sequence', help="This field contains the information related to the numbering of the lines of this order.", required=True, ondelete='cascade'),
                }

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new order
        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of record ids to be process
        @param context: context arguments, like lang, time zone
        @return: return a result
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Purchase Order'
        code = 'purchase.order'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)

    def create(self, cr, uid, vals, context=None):
        '''
        create from purchase_order
        create the sequence for the numbering of the lines
        '''
        vals.update({'sequence_id': self.create_sequence(cr, uid, vals, context)})

        return super(purchase_order, self).create(cr, uid, vals, context)

    def reorder_line_numbering(self, cr, uid, ids, context=None):
        '''
        test function
        '''
        # objects
        tools_obj = self.pool.get('sequence.tools')
        tools_obj.reorder_sequence_number(cr, uid, 'purchase.order', 'sequence_id', 'purchase.order.line', 'order_id', ids, 'line_number', context=context)
        return True

    def allow_resequencing(self, cr, uid, po_browse, context=None):
        '''
        allow resequencing criteria
        '''
        if po_browse.state == 'draft':
            return True
        return False

purchase_order()


class purchase_order_line(osv.osv):
    '''
    override of purchase_order_line class
    '''
    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Line'
    _columns = {'line_number': fields.integer(string='Line', required=True),
                }
    _order = 'line_number, id'

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        if the line_number is not in the default, we set it to False
        '''
        if default is None:
            default = {}
        if context is None:
            context = {}

        # we set line_number, so it will not be copied in copy_data - keepLineNumber - the original Line Number will be kept
        if 'line_number' not in default and not context.get('keepLineNumber', False):
            default.update({'line_number': False})
        return super(purchase_order_line, self).copy_data(cr, uid, id, default, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        check the numbering on deletion
        '''
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # objects
        tools_obj = self.pool.get('sequence.tools')

        if self._name == 'purchase.order.line' and not context.get('skipResequencing', False):
            # re sequencing only happen if purchase order is draft (behavior 1)
            # get ids with corresponding po at draft state
            draft_ids = self.allow_resequencing(cr, uid, ids, context=context)
            tools_obj.reorder_sequence_number_from_unlink(cr, uid, draft_ids, 'purchase.order', 'sequence_id', 'purchase.order.line', 'order_id', 'line_number', context=context)

        return super(purchase_order_line, self).unlink(cr, uid, ids, context=context)

    def allow_resequencing(self, cr, uid, ids, context=None):
        '''
        define if a resequencing has to be performed or not

        return the list of ids for which resequencing will can be performed

        linked to Po + Po allows resequencing
        '''
        # objects
        po_obj = self.pool.get('purchase.order')

        resequencing_ids = [x.id for x in self.browse(cr, uid, ids, context=context) if x.order_id and po_obj.allow_resequencing(cr, uid, x.order_id, context=context)]
        return resequencing_ids

purchase_order_line()


class supplier_catalogue(osv.osv):

    _inherit = 'supplier.catalogue'
    _description = 'Supplier catalogue'
    _columns = {'sequence_id': fields.many2one('ir.sequence', 'Lines Sequence', help="This field contains the information related to the numbering of the lines of this order.", required=True, ondelete='cascade'),
                }

    def create_sequence(self, cr, uid, vals, context=None):
        """
        Create new entry sequence for every new order
        @param cr: cursor to database
        @param user: id of current user
        @param ids: list of record ids to be process
        @param context: context arguments, like lang, time zone
        @return: return a result
        """
        seq_pool = self.pool.get('ir.sequence')
        seq_typ_pool = self.pool.get('ir.sequence.type')

        name = 'Supplier catalogue'
        code = 'supplier.catalogue'

        types = {
            'name': name,
            'code': code
        }
        seq_typ_pool.create(cr, uid, types)

        seq = {
            'name': name,
            'code': code,
            'prefix': '',
            'padding': 0,
        }
        return seq_pool.create(cr, uid, seq)

    def create(self, cr, uid, vals, context=None):
        '''
        create from purchase_order
        create the sequence for the numbering of the lines
        '''
        vals.update({'sequence_id': self.create_sequence(cr, uid, vals, context)})

        return super(supplier_catalogue, self).create(cr, uid, vals, context)

supplier_catalogue()


class supplier_catalogue_line(osv.osv):
    '''
    override of purchase_order_line class
    '''
    _inherit = 'supplier.catalogue.line'
    _description = 'Supplier Catalogue Line'
    _columns = {
        'line_number': fields.integer(string='Line', required=True),
    }
    _order = 'line_number'

    def create(self, cr, uid, vals, context=None):
        '''
        _inherit = 'supplier.catalogue.line'

        add the corresponding line number
        '''
        if self._name != 'supplier.catalogue.merged.line':
            # gather the line number from the sale order sequence
            order = self.pool.get('supplier.catalogue').browse(cr, uid, vals['catalogue_id'], context)
            sequence = order.sequence_id
            line = sequence.get_id(code_or_id='id', context=context)
            vals.update({'line_number': line})

        # create the new sale order line
        result = super(supplier_catalogue_line, self).create(cr, uid, vals, context=context)

        return result

supplier_catalogue_line()

class ir_sequence(osv.osv):
    '''
    override of ir_sequence from account as of a bug when the id is a list
    '''
    _inherit = 'ir.sequence'

    def get_id(self, cr, uid, sequence_id, code_or_id='id', context=None):
        '''
        correct a bug as sequence_id is passed as an array, which
        is not taken into account in the override in account
        '''
        if context is None:
            context = {}
        if isinstance(sequence_id, list):
            return super(ir_sequence, self).get_id(cr, uid, sequence_id[0], code_or_id, context=context)

        return super(ir_sequence, self).get_id(cr, uid, sequence_id, code_or_id, context=context)

    def _get_instance(self, cr, uid):
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        if company and hasattr(company, 'instance_id') and company.instance_id and company.instance_id.po_fo_cost_center_id:
            return company.instance_id.po_fo_cost_center_id.code
        raise osv.except_osv(_('Error'), _('Add the cost center picked for PO/FO reference'))

    def _get_instance_code(self, cr, uid):
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        return company and hasattr(company, 'instance_id') and company.instance_id and company.instance_id.code or ''

    def _get_instance_missioncode(self, cr, uid):
        company = self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id']).company_id
        return company and hasattr(company, 'instance_id') and company.instance_id and company.instance_id.mission or ''

    def _get_hqcode(self, cr, uid):
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        parent_id = company and hasattr(company, 'instance_id') and company.instance_id and company.instance_id.parent_id or False
        code = company and hasattr(company, 'instance_id') and company.instance_id and company.instance_id.po_fo_cost_center_id and company.instance_id.po_fo_cost_center_id.code or ''
        parent_seen = []

        # UFTP-341: If it's an HQ instance, then also take the code of prop instance as the prefix of FO PO
        if parent_id is False:
            code = company and hasattr(company, 'instance_id') and company.instance_id and company.instance_id.code

        while parent_id:
            code = parent_id.po_fo_cost_center_id and parent_id.po_fo_cost_center_id.code or ''

            hq_instance_code = parent_id.code
            parent_id = parent_id.parent_id or False
            if parent_id in parent_seen:
                raise osv.except_osv(_('Error'), _('Loop detected in Proprietary Instance tree, you should have a top level instance without any parent.'))

            # UFTP-341: When it come to HQ code, just take the prop instance code instead of the cost center code, to avoid having same code for different HQs
            if parent_id is False:
                code = hq_instance_code

            parent_seen.append(parent_id)
        return code


    def _process(self, cr, uid, s):
        data = {
            'year':time.strftime('%Y'),
            'month': time.strftime('%m'),
            'day':time.strftime('%d'),
            'y': time.strftime('%y'),
            'doy': time.strftime('%j'),
            'woy': time.strftime('%W'),
            'weekday': time.strftime('%w'),
            'h24': time.strftime('%H'),
            'h12': time.strftime('%I'),
            'min': time.strftime('%M'),
            'sec': time.strftime('%S'),
        }
        if s:
            if '%(instance)s' in s:
                data['instance'] = self._get_instance(cr, uid)
            if '%(hqcode)s' in s:
                data['hqcode'] = self._get_hqcode(cr, uid)
            if '%(instance_code)s' in s:
                data['instance_code'] = self._get_instance_code(cr, uid)
            if '%(missioncode)s' in s:
                data['missioncode'] = self._get_instance_missioncode(cr, uid)

        return (s or '') % data
ir_sequence()

