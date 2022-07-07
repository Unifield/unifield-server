# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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
from tools.translate import _
import netsvc

from lxml import etree


# DOCUMENT DATA dict : {'document.model': ('document.line.model',
#                                          'field linked to document.model on document.line.model',
#                                          'field linked to document.line.model on document.model',
#                                          'field with the quantity in document.line.model',
#                                          'domain to apply on document.line.model')}
"""
This dictionnary is used by the document.cancel.line and wizard.cancel.lines
objects to get the different relation between a parent document and its lines.

The dictionnary keys are the parent document model and the values of the dict
are a tuple with information in this order :
    * model of the line for the parent document
    * field of the line that link the line to its parent
    * field of the parent that contains the lines
    * field with the quantity for the line
    * domain to apply on lines (e.g. : only draft stock moves on picking)
"""
DOCUMENT_DATA = {
    'purchase.order': ('purchase.order.line', 'order_id', 'order_line', 'product_qty', ''),
    'sale.order': ('sale.order.line', 'order_id', 'order_line', 'product_uom_qty', ''),
}


def bcl(self, cr, uid, ids, context=None):
    '''
    Call the wizard to cancel lines
    '''
    context = context is None and {} or context

    if isinstance(ids, (int, long)):
        ids = [ids]

    # If there is no line to cancel.
    for obj in self.browse(cr, uid, ids, context=context):
        if not obj[DOCUMENT_DATA.get(self._name)[2]]:
            raise osv.except_osv(_('Error'), _('No line to cancel'))

    context.update({
        'active_id': ids[0],
        'from_cancel_wizard': True,
        'active_model': self._name,
    })

    to_return = {
        'type': 'ir.actions.act_window',
        'res_model': 'wizard.cancel.lines',
        'view_type': 'form',
        'view_mode': 'form',
        'target': 'new',
        'context': context
    }

    wiz_fields = {}
    # Add the selected lines by default if they are available
    if self._name in ('sale.order', 'purchase.order') and context.get('button_selected_ids'):
        domain = [('id', 'in', context['button_selected_ids'])]
        if self._name == 'sale.order':
            line_obj = self.pool.get('sale.order.line')
            domain.append(('state', 'in', ['draft', 'validated']))
        else:
            line_obj = self.pool.get('purchase.order.line')
            domain.append(('state', 'in', ['draft', 'validated_n', 'validated']))
        line_ids = line_obj.search(cr, uid, domain, context=context)
        if line_ids:
            wiz_fields.update({'line_ids': line_ids, 'has_sel_lines': True})
    # To display cancel & resource for PO from FO/IR
    if self._name == 'purchase.order':
        po = self.browse(cr, uid, ids[0], fields_to_fetch=['po_from_fo', 'po_from_ir'], context=context)
        if po.po_from_fo or po.po_from_ir:
            wiz_fields.update({'sourced_po': True})

    if wiz_fields:
        wiz_id = self.pool.get('wizard.cancel.lines').create(cr, uid, wiz_fields, context=context)
        to_return.update({'res_id': wiz_id})

    # Return the wizard to display lines to cancel
    return to_return

"""
All the following documents will call the same button_cancel_lines method
to cancel some or all lines on documents.

Documents which inherit from document.cancel.line:
    * Purchase Order
    * Field Order / Internal request
"""


class purchase_order(osv.osv):
    _name = 'purchase.order'
    _inherit = 'purchase.order'

    def button_cancel_lines(self, cr, uid, ids, context=None):
        return bcl(self, cr, uid, ids, context=context)


class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def button_cancel_lines(self, cr, uid, ids, context=None):
        return bcl(self, cr, uid, ids, context=context)


## Object initializations ##

purchase_order()
sale_order()

#### END OF INHERITANCE OF DOCUMENTS ####

"""
All the following documents will call the same fields_view_get to
display the good tree/search view if a tree/search view is defined
for the document wizard deletion.

Documents:
    * Purchase Order lines
    * Field Order / Internal request lines
"""


def cancel_fields_view_get(self, cr, uid, view_id, view_type, context=None):
    '''
    Check if a view exist for the object (self) and the view type (view_type)
    '''
    if context is None:
        context = {}

    if view_id:
        return view_id

    # If we don't coming from cancel lines wizard
    if not context.get('from_cancel_wizard') or view_type not in ('tree', 'search'):
        return None

    data_obj = self.pool.get('ir.model.data')
    view_name = '%s_%s_cancel_view' % (self._name.replace('.', '_'), view_type)
    try:
        res = None
        view = data_obj.get_object_reference(cr, uid, 'msf_doc_import', view_name)
        if view:
            res = view[1]
    except ValueError:
        res = None

    return res


def noteditable_fields_view_get(res, view_type, context=None):
    '''
    Make the list of lines not editable
    '''
    if context is None:
        context = {}

    if context.get('from_cancel_wizard') and view_type == 'tree':
        root = etree.fromstring(res['arch'])
        fields = root.xpath('/tree')
        for field in fields:
            root.set('noteditable', 'True')
            if context.get('procurement_request'):
                root.set('string', 'Internal request lines')
        res['arch'] = etree.tostring(root)

    return res


class purchase_order_line(osv.osv):
    _inherit = 'purchase.order.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}

        if context.get('initial_doc_id', False) and context.get('initial_doc_type', False) == 'purchase.order':
            rfq_ok = self.pool.get('purchase.order').browse(cr, uid, context.get('initial_doc_id'), context=context).rfq_ok
            context['rfq_ok'] = rfq_ok
        view_id = cancel_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(purchase_order_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)

    def cancel_and_resource_pol(self, cr, uid, ids, context=None):
        '''
        Cancel and resource the given PO lines
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        po_obj = self.pool.get('purchase.order')
        wf_service = netsvc.LocalService("workflow")

        # cancel and resource line:
        for pol in self.browse(cr, uid, ids, fields_to_fetch=['order_id', 'has_pol_been_synched'], context=context):
            if pol.has_pol_been_synched:
                raise osv.except_osv(_('Warning'), _('You cannot cancel a purchase order line which has already been synchronized'))
            wf_service.trg_validate(uid, 'purchase.order.line', pol.id, 'cancel_r', cr)

            # Create the counterpart FO to a loan PO with an external partner if non-cancelled lines have been confirmed
            p_order = pol.order_id
            if p_order and p_order.order_type == 'loan' and not p_order.is_a_counterpart\
                    and p_order.partner_type == 'external' and p_order.state == 'confirmed':
                self.create_counterpart_fo_for_external_partner_po(cr, uid, p_order, context=context)

            # check if the related CV should be set to Done
            if p_order:
                po_obj.check_close_cv(cr, uid, p_order.id, context=context)

        return True


class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}

        if context.get('initial_doc_id', False) and context.get('initial_doc_type', False) == 'sale.order':
            proc_request = self.pool.get('sale.order').browse(cr, uid, context.get('initial_doc_id'), context=context).procurement_request
            context['procurement_request'] = proc_request

        view_id = cancel_fields_view_get(self, cr, uid, view_id, view_type, context=context)
        res = super(sale_order_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        return noteditable_fields_view_get(res, view_type, context)


purchase_order_line()
sale_order_line()

### END OF INHERITANCE ###


class wizard_cancel_lines(osv.osv_memory):
    """
    Wizard to cancel lines of document.

    The displaying of lines to cancel is dynamically build according to
    the initial_doc_type given (see fields_get method).
    """
    _name = 'wizard.cancel.lines'

    _columns = {
        'initial_doc_id': fields.integer(string='ID of the initial document', required=True),
        'initial_doc_type': fields.char(size=128, string='Model of the initial document', required=True),
        'to_cancel_type': fields.char(size=128, string='Model of the lines', required=True),
        'linked_field_name': fields.char(size=128, string='Field name of the link between lines and original doc', required=True),
        'qty_field': fields.char(size=128, string='Qty field used to select only empty lines'),
        'has_sel_lines': fields.boolean(string='Lines have been selected before the wizard'),
        'sourced_po': fields.boolean(string='The document linked to the lines is a PO sourced from a FO or an IR'),
        # The line_ids field is a text field, but the content of this field is the result of the many2many field creation (like [(6,0,[IDS])]).
        # On the cancel_selected_lines method, we parse this content to get id of the lines to cancel.
        'line_ids': fields.text(string='Line ids'),
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        '''
        Check if the wizard has been overrided
        '''
        context = context is None and {} or context

        res = super(wizard_cancel_lines, self).default_get(cr, uid, fields, context=context, from_web=from_web)

        # Set the different data which are coming from the context
        if 'active_id' in context:
            res['initial_doc_id'] = context.get('active_id')

        if 'active_model' in context and context.get('active_model') in DOCUMENT_DATA:
            res['initial_doc_type'] = context.get('active_model')
            res['to_cancel_type'] = DOCUMENT_DATA.get(context.get('active_model'))[0]
            res['linked_field_name'] = DOCUMENT_DATA.get(context.get('active_model'))[1]
            res['qty_field'] = DOCUMENT_DATA.get(context.get('active_model'))[3]

        return res

    def cancel_resource_selected_lines(self, cr, uid, ids, context=None):
        return self.cancel_selected_lines(cr, uid, ids, context=context, resource=True)

    def cancel_selected_lines(self, cr, uid, ids, context=None, resource=False):
        '''
        Cancel only the selected lines
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            line_obj = self.pool.get(wiz.to_cancel_type)
            line_ids = []
            # Parse the content of 'line_ids' field (text field) to retrieve the id of lines to cancel.
            for line in wiz.line_ids:
                for l in line[2]:
                    line_ids.append(l)
            if not line_ids:
                return {'type': 'ir.actions.act_window_close'}

            context.update({
                'noraise': True,
                'from_cancel_wizard': True,
            })
            # Method to cancel FO/IR/PO line
            if resource and wiz.initial_doc_type == 'purchase.order':  # Cancel & resource PO line(s)
                line_obj.cancel_and_resource_pol(cr, uid, line_ids, context=context)
            else:
                netsvc.LocalService("workflow").trg_validate(uid, wiz.to_cancel_type, line_ids, 'cancel', cr)

        context['from_cancel_wizard'] = False

        return {'type': 'ir.actions.act_window_close'}

    def select_empty_lines(self, cr, uid, ids, context=None):
        '''
        Add empty lines
        '''
        return self.select_all_lines(cr, uid, ids, context=context, select_only_empty=True)

    def select_all_lines(self, cr, uid, ids, context=None, select_only_empty=False):
        '''
        Select all lines of the initial document
        '''
        context = context is None and {} or context
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            if select_only_empty and not wiz.qty_field:
                raise osv.except_osv(_('Error'), _('The select empty lines is not available for this document'))

            line_obj = self.pool.get(wiz.to_cancel_type)
            if select_only_empty:
                line_ids = line_obj.search(cr, uid, [(wiz.linked_field_name, '=', wiz.initial_doc_id), (wiz.qty_field, '=', 0.00)], context=context)
            else:
                line_ids = line_obj.search(cr, uid, [(wiz.linked_field_name, '=', wiz.initial_doc_id)], context=context)

            if wiz.to_cancel_type in ['sale.order.line', 'purchase.order.line']:
                states = ['draft', 'validated']
                if wiz.to_cancel_type == 'purchase.order.line':
                    states.append('validated_n')
                line_ids = line_obj.search(cr, uid, [('id', 'in', line_ids), ('state', 'in', states)], context=context)

            self.write(cr, uid, [wiz.id], {'line_ids': line_ids}, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': ids and wiz.id or False,
            'context': context,
            'target': 'new',
        }

    def fields_get(self, cr, uid, fields=None, context=None, with_uom_rounding=False):
        '''
        On this fields_get method, we build the line_ids field.
        The line_ids field is defined as a text field but, for users, this
        field should be displayed as a many2many that allows us to select
        lines of document to cancel.
        The line_ids field is changed to a many2many field according to the
        data in DOCUMENT_DATA (see top of this file).
        '''
        context = context is None and {} or context

        res = super(wizard_cancel_lines, self).fields_get(cr, uid, fields, context=context)

        if context.get('active_model') and DOCUMENT_DATA.get(context.get('active_model')):
            ddata = DOCUMENT_DATA.get(context.get('active_model'))
            line_obj = ddata[0]
            if not ddata[4]:
                domain = "[('%s', '=', initial_doc_id)]" % ddata[1]
            else:
                domain = "[%s, ('%s', '=', initial_doc_id)]" % (ddata[4], ddata[1])
            res.update(line_ids={'related_columns': ['wiz_id', 'line_id'],
                                 'relation': line_obj,
                                 'string': 'Lines to cancel',
                                 'context': context,
                                 'third_table': '%sto_cancel' % line_obj.replace('.', '_'),
                                 'selectable': True,
                                 'type': 'many2many',
                                 'domain': "%s" % domain})

        return res


wizard_cancel_lines()
