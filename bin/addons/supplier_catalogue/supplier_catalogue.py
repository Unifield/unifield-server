##############################################################################
# -*- coding: utf-8 -*-
#
#    OpenERP, Open Source Management Solution
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

from osv import osv
from osv import fields

from tools.translate import _
from tools.misc import _get_std_mml_status
from datetime import date, datetime


import decimal_precision as dp

import time

import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator

_HEADER_TYPE = {type('char'): 'string',
                type(1): 'number',
                type(1.00): 'number',
                type(int(1)): 'number',
                type(datetime.now()): 'datetime'}

class supplier_catalogue(osv.osv):
    _name = 'supplier.catalogue'
    _description = 'Supplier catalogue'
    _order = 'period_from, period_to'
    _trace = True

    def copy(self, cr, uid, catalogue_id, default=None, context=None):
        '''
        Disallow the possibility to duplicate a catalogue.
        '''
        raise osv.except_osv(_('Error'), _('You cannot duplicate a catalogue !'))

        default = default or {}
        default.update({'state': 'draft'})

        return False

    def open_new_catalogue_form(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context['partner_id'] = ids[0]
        partner_obj = self.pool.get('res.partner')
        if partner_obj.search(cr, uid, [('id', '=', ids[0]), ('partner_type', '=', 'esc')], context=context) and \
                self.pool.get('res.company')._get_instance_level(cr, uid) != 'section':
            raise osv.except_osv(_('Error'), 'For an ESC Supplier you must create the catalogue on a HQ instance.')

        return {
            'res_model': 'supplier.catalogue',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'type': 'ir.actions.act_window',
            'context': context,
            'domain': [('partner_id', '=', ids[0])],
        }

    def create(self, cr, uid, vals, context=None):
        '''
        Check if the new values override a catalogue
        '''
        if context is None:
            context = {}

        res = super(supplier_catalogue, self).create(cr, uid, vals, context=context)

        # UTP-746: now check if the partner is inactive, then set this catalogue also to become inactive
        catalogue = self.browse(cr, uid, [res], fields_to_fetch=['partner_id'], context=context)[0]
        if not catalogue.partner_id.active:
            self.write(cr, uid, [res], {'active': False}, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        # forbid supplier catalogue coming from higher instance level to be manually deleted:
        to_unlink = set()
        for catalogue in self.read(cr, uid, ids, ['from_sync'], context=context):
            if not catalogue['from_sync'] or context.get('sync_update_execution', False):
                to_unlink.add(catalogue['id'])
            else:
                raise osv.except_osv(
                    _('Error'),
                    _('Warning! You cannot delete a synched supplier catalogue created in a higher instance level.')
                )

        return super(supplier_catalogue, self).unlink(cr, uid, list(to_unlink), context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update the supplierinfo and pricelist line according to the
        new values
        '''
        if not ids:
            return True
        ir_model = self.pool.get('ir.model')
        supinfo_obj = self.pool.get('product.supplierinfo')
        price_obj = self.pool.get('pricelist.partnerinfo')
        user_obj = self.pool.get('res.users')
        line_obj = self.pool.get('supplier.catalogue.line')
        partner_obj = self.pool.get('res.partner')

        if context is None:
            context = {}

        to_be_confirmed = False
        for catalogue in self.browse(cr, uid, ids, context=context):
            if catalogue.from_sync and not context.get('sync_update_execution'):
                for val in vals:
                    if val != 'active':
                        raise osv.except_osv(_('Error'), _('You can not modify a catalogue created from sync'))
            # Track Changes
            if catalogue.state != 'draft' and vals.get('active') is not None and vals['active'] != catalogue.active:
                for line in catalogue.line_ids:
                    has_removed = False
                    if line.product_id:
                        old_seller = []
                        for seller in line.product_id.seller_ids:
                            old_seller.append((seller.sequence, seller.name.name))
                        new_seller = list(old_seller)
                        for i, seller in enumerate(new_seller):
                            if catalogue.partner_id.name in seller[1]:
                                new_seller.remove(new_seller[i])
                                has_removed = True
                                break
                        if vals['active'] and not has_removed:
                            new_seller.append((0, catalogue.partner_id.name))
                        object_id = ir_model.search(cr, uid, [('model', '=', 'product.template')], context=context)[0]
                        supinfo_obj.add_audit_line(cr, uid, 'seller_ids', object_id, line.product_id.id, False, False, False,
                                                   self.pool.get('product.template')._columns['seller_ids'].string,
                                                   False, new_seller, old_seller, context=context)

            current_partner_id = user_obj.browse(cr, uid, uid, context=context).company_id.partner_id.id
            if 'partner_id' in vals and vals['partner_id'] != catalogue.partner_id.id:
                if vals['partner_id'] == current_partner_id:
                    # If the new partner is the instance partner, remove the supplier info
                    supplierinfo_ids = supinfo_obj.search(cr, uid,
                                                          [('catalogue_id', 'in', ids)], order='NO_ORDER', context=context)
                    supinfo_obj.unlink(cr, uid, supplierinfo_ids, context=context)
                elif catalogue.partner_id.id == current_partner_id:
                    # If the catalogue was for teh instance partner, set it to False, then confirm it again
                    to_be_confirmed.append(catalogue.id)

            # Update product pricelists only if the catalogue is confirmed
            if vals.get('state', catalogue.state) == 'confirmed':
                if not to_be_confirmed:
                    new_supinfo_vals = {}

                    # Change the partner of all supplier info instances
                    if 'partner_id' in vals and vals['partner_id'] != catalogue.partner_id.id:
                        delay = partner_obj.browse(cr, uid, vals['partner_id'], context=context).default_delay
                        new_supinfo_vals.update({'name': vals['partner_id'], 'delay': delay})

                    # Change pricelist data according to new data (only if there is change)
                    new_price_vals = {}
                    for prop in ('period_to', 'period_from', 'currency_id', 'name'):
                        if prop in vals:
                            if prop == 'period_to':
                                new_price_vals['valid_till'] = vals[prop]
                            elif prop == 'period_from':
                                new_price_vals['valid_from'] = vals[prop]
                            else:
                                new_price_vals[prop] = vals[prop]

                    # Update the supplier info and price lines
                    supplierinfo_ids = supinfo_obj.search(cr, uid,
                                                          [('catalogue_id', 'in', ids)], order='NO_ORDER', context=context)
                    if new_supinfo_vals:
                        supinfo_obj.write(cr, uid, supplierinfo_ids, new_supinfo_vals, context=context)

                    pricelist_ids = []
                    if 'line_ids' in vals:
                        # lines are being edited
                        line_ids = [x[1] for x in vals['line_ids'] if x]
                        line_result = line_obj.read(cr, uid, line_ids, ['partner_info_id'], context=context)
                        pricelist_ids = [x['partner_info_id'][0] for x in line_result if x['partner_info_id']]

                    if new_price_vals:
                        # the catalog itself has been edited, all the related lines
                        # should be updated accordingly (that could be long operation)
                        cr.execute('''SELECT partner_info_id FROM supplier_catalogue_line 
                            WHERE catalogue_id = %s ''', (ids[0],))
                        pricelist_ids = [x[0] for x in cr.fetchall() if x[0]]
                        price_obj.write(cr, uid, pricelist_ids, new_price_vals, context=context)

                # Check products if the periods are changed or the catalogue activated
                if vals.get('active') is True or (catalogue.active and
                                                  (('period_from' in vals and vals['period_from'] != catalogue.period_from)
                                                   or ('period_to' in vals and vals['period_to'] != catalogue.period_to))):
                    if 'period_from' in vals:
                        period_from = vals['period_from']
                    else:
                        period_from = catalogue.period_from
                    if 'period_to' in vals:
                        period_to = vals['period_to']
                    else:
                        period_to = catalogue.period_to
                    invalid_prods = self.check_cat_prods_valid(cr, uid, catalogue.id, [], period_from, period_to, context=context)
                    if invalid_prods:
                        raise osv.except_osv(_('Warning!'),
                                             _('This catalogue contains the product(s) %s which are duplicate(s) of another catalogue for the same supplier! Please remove the product(s) from this/other catalogue before confirming')
                                             % (', '.join(invalid_prods),))

        res = super(supplier_catalogue, self).write(cr, uid, ids, vals, context=context)

        # Confirm the catalogue in case of partner change from instance partner to other partner
        if to_be_confirmed:
            self.button_draft(cr, uid, to_be_confirmed, context=context)
            self.button_confirm(cr, uid, to_be_confirmed, context=context)

        return res

    def button_confirm(self, cr, uid, ids, context=None):
        '''
        Confirm the catalogue and all lines
        '''
        ids = isinstance(ids, int) and [ids] or ids
        line_obj = self.pool.get('supplier.catalogue.line')

        line_ids = line_obj.search(cr, uid, [('catalogue_id', 'in', ids)], order='NO_ORDER', context=context)

        catalogues = self.read(cr, uid, ids, ['state', 'active'], context=context)
        if not all(x['state'] == 'draft' for x in catalogues):
            raise osv.except_osv(_('Error'), _('The catalogue you try to confirm is already confirmed. Please reload the page to update the status of this catalogue'))

        # US-12606: Check if the products exist in another valid catalogue
        for catalogue in catalogues:
            if catalogue['active']:
                invalid_prods = self.check_cat_prods_valid(cr, uid, catalogue['id'], [], None, None, context=context)
                if invalid_prods:
                    raise osv.except_osv(_('Warning!'), _('This catalogue contains the product(s) %s which are duplicate(s) of another catalogue for the same supplier! Please remove the product(s) from this/other catalogue before confirming')
                                         % (', '.join(invalid_prods),))

        # Update catalogues
        self.write(cr, uid, ids, {'state': 'confirmed'}, context=context)

        # Update lines, this is required as many operations are done in the
        # supplier.catatogue.line.write() when the catalog state change
        line_obj.write(cr, uid, line_ids, {}, context=context)

        return True

    def button_draft(self, cr, uid, ids, context=None):
        '''
        Reset to draft the catalogue
        '''
        ids = isinstance(ids, int) and [ids] or ids
        #line_obj = self.pool.get('supplier.catalogue.line')
        ir_model = self.pool.get('ir.model')
        supplinfo_obj = self.pool.get('product.supplierinfo')

        #line_ids = line_obj.search(cr, uid, [('catalogue_id', 'in', ids)], context=context)

        if not all(x['state'] == 'confirmed' for x in self.read(cr, uid, ids, ['state'], context=context)):
            raise osv.except_osv(_('Error'), _('The catalogue you try to confirm is already in draft state. Please reload the page to update the status of this catalogue'))

        # Update catalogues
        self.write(cr, uid, ids, {'state': 'draft'}, context=context)

        # US-3531: Add a Track Changes line to each product in the catalogue
        catalog = self.browse(cr, uid, ids[0], fields_to_fetch=['partner_id', 'line_ids'], context=context)
        for line in catalog.line_ids:
            if line.product_id:
                old_seller = []
                for seller in line.product_id.seller_ids:
                    old_seller.append((seller.sequence, seller.name.name))
                new_seller = list(old_seller)
                for i, seller in enumerate(new_seller):
                    if catalog.partner_id.name in seller[1]:
                        new_seller.remove(new_seller[i])
                        break
                object_id = ir_model.search(cr, uid, [('model', '=', 'product.template')], context=context)[0]
                supplinfo_obj.add_audit_line(cr, uid, 'seller_ids', object_id, line.product_id.id, False, False,
                                             False, self.pool.get('product.template')._columns['seller_ids'].string,
                                             False, new_seller, old_seller, context=context)

        # Update lines
        #line_obj.write(cr, uid, line_ids, {}, context=context)
        #utp1033
        cr.execute('''delete from pricelist_partnerinfo
                      where id in (select partner_info_id
                                    from supplier_catalogue_line
                                    where catalogue_id = %s)''', (ids[0],))
        cr.execute('''delete from product_supplierinfo
                        where id in (select supplier_info_id
                                    from supplier_catalogue_line
                                     where catalogue_id = %s)
                        and id not in (select suppinfo_id from
                                    pricelist_partnerinfo ) ''', (ids[0],))

        return True

    def name_get(self, cr, uid, ids, context=None):
        '''
        Add currency to the name of the catalogue
        '''
        res = []

        for r in self.browse(cr, uid, ids, context=context):
            res.append((r.id, '%s (%s)' % (r.name, r.currency_id.name)))

        return res

    def _search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
        '''
        If the search is called from the catalogue line list view, returns only catalogues of the
        partner defined in the context
        '''
        if not context:
            context = {}

        if context.get('search_default_partner_id', False):
            args.append(('partner_id', '=', context.get('search_default_partner_id', False)))

        return super(supplier_catalogue, self)._search(cr, uid, args, offset,
                                                       limit, order, context, count, access_rights_uid)

    def _get_active(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Return True if today is into the period of the catalogue
        '''
        res = {}

        for catalogue in self.browse(cr, uid, ids, context=context):
            date_from = False
            date_to = False

            if catalogue.period_from:
                date_from = datetime.strptime(catalogue.period_from, '%Y-%m-%d')
            if catalogue.period_to:
                date_to = datetime.strptime(catalogue.period_to, '%Y-%m-%d')

            if date_from and date_to:
                res[catalogue.id] = date_from < datetime.now() < date_to
            elif date_from:
                res[catalogue.id] = date_from < datetime.now()
            elif date_to:
                res[catalogue.id] = datetime.now() < date_to
            else:
                res[catalogue.id] = True

        return res

    def _search_active(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all active catalogues
        '''
        ids = []

        for arg in args:
            if arg[0] == 'current' and arg[1] == '=':
                ids = self.search(cr, uid, [('period_from', '<', date.today()),
                                            ('period_to', '>', date.today())], context=context)
                return [('id', 'in', ids)]
            elif arg[0] == 'current' and arg[1] == '!=':
                ids = self.search(cr, uid, ['|', ('period_from', '>', date.today()),
                                            ('period_to', '<', date.today())], context=context)
                return [('id', 'in', ids)]

        return ids

    def _is_esc_from_partner_id(self, cr, uid, partner_id, context=None):
        """Is an ESC Supplier Catalog ? (from partner id)"""
        if not partner_id:
            return False
        rs = self.pool.get('res.partner').read(cr, uid, [partner_id],
                                               ['partner_type'],
                                               context=context)
        if rs and rs[0] and rs[0]['partner_type'] \
           and rs[0]['partner_type'] == 'esc':
            return True
        return False

    def _is_esc(self, cr, uid, ids, fieldname, args, context=None):
        """Is an ESC Supplier Catalog ?"""
        res = {}
        if not ids:
            return res
        if isinstance(ids, int):
            ids = [ids]
        for r in self.read(cr, uid, ids, ['partner_id'],
                           context=context):
            res[r['id']] = False
            if r['partner_id']:
                res[r['id']] = self._is_esc_from_partner_id(cr, uid,
                                                            r['partner_id'][0],
                                                            context=context)

        return res

    def _is_from_sync(self, cr, uid, ids, fieldname, args, context=None):
        """
        Has the catalogue been created by sync ?
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        res = {}
        if not ids:
            return res
        entity_identifier = self.pool.get('sync.client.entity').get_entity(cr, uid, context).identifier
        for cat in self.read(cr, uid, ids, ['partner_id'], context=context):
            catalogue_sd_ref = self.get_sd_ref(cr, uid, cat['id'])
            res[cat['id']] = catalogue_sd_ref and not catalogue_sd_ref.startswith(entity_identifier) or False

        return res

    def _get_instance_level(self, cr, uid, ids, field_name, args, context=None):
        level = self.pool.get('res.company')._get_instance_level(cr, uid)
        res = {}
        for _id in ids:
            res[_id] = level
        return res

    _columns = {
        'name': fields.char(size=64, string='Name', required=True),
        'partner_id': fields.many2one('res.partner', string='Partner', required=True,
                                      domain=[('supplier', '=', True)], select=1),
        'period_from': fields.date(string='From',
                                   help='Starting date of the catalogue.'),
        'period_to': fields.date(string='To',
                                 help='End date of the catalogue'),
        'currency_id': fields.many2one('res.currency', string='Currency', required=True,
                                       help='Currency used in this catalogue.'),
        'comment': fields.text(string='Comment'),
        'line_ids': fields.one2many('supplier.catalogue.line', 'catalogue_id', string='Lines'),
        'supplierinfo_ids': fields.one2many('product.supplierinfo', 'catalogue_id', string='Supplier Info.'),
        'active': fields.boolean(string='Active'),
        'current': fields.function(_get_active, fnct_search=_search_active, method=True, string='Active', type='boolean', store=False,
                                   readonly=True, help='Indicate if the catalogue is currently active.'),
        'file_to_import': fields.binary(string='File to import', filters='*.xml',
                                        help="""The file should be in XML Spreadsheet 2003 format. The columns should be in this order :
                                        Product Code*, Product Description, Product UoM*, Min Quantity*, Unit Price*, SoQ Rounding, Min Order Qty, Comment."""),
        'data': fields.binary(string='File with errors',),
        'filename': fields.char(string='Lines not imported', size=256),
        'filename_template': fields.char(string='Template', size=256),
        'import_error_ok': fields.boolean('Display file with error'),
        'text_error': fields.text('Text Error', readonly=True),
        'esc_update_ts': fields.datetime('Last updated on', readonly=True),  # UTP-746 last update date for ESC Supplier
        'is_esc': fields.function(_is_esc, type='boolean', string='Is ESC Supplier', method=True),
        'state': fields.selection([('draft', 'Draft'), ('confirmed', 'Confirmed')], string='State', required=True, readonly=True),
        'from_sync': fields.function(_is_from_sync, type='boolean', string='Created by Sync', method=True),
        'instance_level': fields.function(_get_instance_level, string='Instance Level', type='char', method=True),
    }

    _defaults = {
        # By default, use the currency of the user
        'currency_id': lambda obj, cr, uid, ctx: obj.pool.get('res.users').browse(cr, uid, uid, context=ctx).company_id.currency_id.id,
        'partner_id': lambda obj, cr, uid, ctx: ctx.get('partner_id', False),
        'period_from': lambda *a: time.strftime('%Y-%m-%d'),
        'active': lambda *a: True,
        'filename_template': 'template.xls',
        'state': lambda *a: 'draft',
        'instance_level': lambda obj, cr, uid, ctx: obj.pool.get('res.company')._get_instance_level(cr, uid),
    }

    def _check_period(self, cr, uid, ids):
        '''
        Check if the To date is older than the From date
        '''
        for catalogue in self.browse(cr, uid, ids):
            if catalogue.period_to and catalogue.period_to < catalogue.period_from:
                return False
        return True

    _constraints = [(_check_period, 'The \'To\' date mustn\'t be younger than the \'From\' date !', ['period_from', 'period_to'])]

    def open_lines(self, cr, uid, ids, context=None):
        '''
        Opens all lines of this catalogue
        '''
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}

        cat = self.browse(cr, uid, ids[0], context=context)
        name = '%s - %s' % (cat.partner_id.name, cat.name)

        context.update({'search_default_partner_id': cat.partner_id.id,})

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'supplier_catalogue', 'non_edit_supplier_catalogue_line_tree_view')[1]

        return {'type': 'ir.actions.act_window',
                'name': name,
                'res_model': 'supplier.catalogue.line',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'view_id': [view_id],
                'domain': [('catalogue_id', '=', ids[0])],
                'context': context}

    def edit_catalogue(self, cr, uid, ids, context=None):
        '''
        Open an edit view of the selected catalogue
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        return {'type': 'ir.actions.act_window',
                'res_model': 'supplier.catalogue',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'context': context}

    def export_file_with_error(self, cr, uid, ids, *args, **kwargs):
        """
        Export lines with errors in a file.
        Warning: len(columns_header) == len(lines_not_imported)
        """
        columns_header = [('Product code*', 'string'), ('Product description', 'string'), ('Product UoM*', 'string'),
                          ('Min Quantity*', 'number'), ('Unit Price*', 'number'), ('SoQ Rounding', 'number'), ('Min Order Qty', 'number'),
                          ('Comment', 'string')]
        lines_not_imported = [] # list of list
        t_dt = type(datetime.now())
        for line in kwargs.get('line_with_error'):
            for f in line:
                if type(f) == t_dt:
                    new_f = f.strftime('%Y-%m-%dT%H:%M:%S.000')
                    line[line.index(f)] = (new_f, 'DateTime')
                elif isinstance(f, str) and 0 <= line.index(f) < len(columns_header) and columns_header[line.index(f)][1] != 'string':
                    try:
                        line[line.index(f)] = (float(f), 'Number')
                    except:
                        line[line.index(f)] = (f, 'String')

            if len(line) < len(columns_header):
                lines_not_imported.append(line + ['' for x in range(len(columns_header)-len(line))])
            else:
                lines_not_imported.append(line)

        files_with_error = SpreadsheetCreator('Lines with errors', columns_header, lines_not_imported)
        vals = {'data': base64.b64encode(files_with_error.get_xml(['decode.utf8'])),
                'filename': 'Lines_Not_Imported.xls',
                'import_error_ok': True}
        return vals

    def catalogue_import_lines(self, cr, uid, ids, context=None):
        '''
        Import the catalogue lines
        '''
        if not context:
            context = {}
        vals = {}
        vals['line_ids'], error_list, line_with_error = [], [], []
        msg_to_return = _("All lines successfully imported")
        ignore_lines = 0

        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')
        wiz_common_import = self.pool.get('wiz.common.import')
        obj_catalog_line = self.pool.get('supplier.catalogue.line')

        date_format = self.pool.get('date.tools').get_db_date_format(cr, uid, context=context)

        for obj in self.browse(cr, uid, ids, context=context):
            if not obj.file_to_import:
                raise osv.except_osv(_('Error'), _('Nothing to import.'))

            fileobj = SpreadsheetXML(xmlstring=base64.b64decode(obj.file_to_import))
            rows,reader = fileobj.getRows(), fileobj.getRows() # because we got 2 iterations
            # take all the lines of the file in a list of dict
            file_values = wiz_common_import.get_file_values(cr, uid, ids, rows, False, error_list, False, context)

            next(reader)
            line_num = 1
            for row in reader:
                error_list_line = []
                to_correct_ok = False
                row_len = len(row)
                if row_len != 8:
                    error_list_line.append(_("You should have exactly 8 columns in this order: Product code*, Product description, Product UoM*, Min Quantity*, Unit Price*, SoQ Rounding, Min Order Qty, Comment."))
                comment = []
                p_comment = False
                #Product code
                try:
                    product_code = row.cells[0].data
                except TypeError:
                    product_code = row.cells[0].data
                except ValueError:
                    product_code = row.cells[0].data
                if not product_code or row.cells[0].type != 'str':
                    default_code = obj_data.get_object_reference(cr, uid, 'msf_doc_import','product_tbd')[1]
                    to_correct_ok = True
                    error_list_line.append(_("The product was not defined properly."))
                else:
                    try:
                        product_code = product_code.strip()
                        code_ids = product_obj.search(cr, uid, [('default_code', '=', product_code)])
                        if not code_ids:
                            default_code = obj_data.get_object_reference(cr, uid, 'msf_doc_import','product_tbd')[1]
                            to_correct_ok = True
                            error_list_line.append(_("The product '%s' was not found.") % product_code)
                        else:
                            default_code = code_ids[0]
                    except Exception:
                        default_code = obj_data.get_object_reference(cr, uid, 'msf_doc_import','product_tbd')[1]
                        to_correct_ok = True
                        error_list_line.append(_("The product '%s' was not found.") % product_code)

                #Product UoM
                p_uom = len(row.cells)>=3 and row.cells[2].data
                if not p_uom:
                    uom_id = obj_data.get_object_reference(cr, uid, 'msf_doc_import','uom_tbd')[1]
                    to_correct_ok = True
                    error_list_line.append(_("The UoM '%s' was not found.") % p_uom)
                else:
                    try:
                        uom_name = p_uom.strip()
                        uom_ids = uom_obj.search(cr, uid, [('name', '=', uom_name)], context=context)
                        if not uom_ids:
                            uom_id = obj_data.get_object_reference(cr, uid, 'msf_doc_import','uom_tbd')[1]
                            error_list_line.append(_("The UoM '%s' was not found.") % uom_name)
                            to_correct_ok = True
                        else:
                            uom_id = uom_ids[0]
                    except Exception:
                        uom_id = obj_data.get_object_reference(cr, uid, 'msf_doc_import','uom_tbd')[1]
                        error_list_line.append(_("The UoM '%s' was not found.") % p_uom)
                        to_correct_ok = True
                #[utp-129]: check consistency of uom
                # I made the check on uom_id according to the constraint _check_uom in unifield-addons/product/product.py (l.744) so that we keep the consistency even when we create a supplierinfo directly from the product
                if default_code != obj_data.get_object_reference(cr, uid, 'msf_doc_import','product_tbd')[1]:
                    if not self.pool.get('uom.tools').check_uom(cr, uid, default_code, uom_id, context):
                        browse_uom = uom_obj.browse(cr, uid, uom_id, context)
                        browse_product = product_obj.browse(cr, uid, default_code, context)
                        uom_id = browse_product.uom_id.id
                        to_correct_ok = True
                        error_list_line.append(_('The UoM "%s" was not consistent with the UoM\'s category ("%s") of the product "%s".'
                                                 ) % (browse_uom.name, browse_product.uom_id.category_id.name, browse_product.default_code))

                #Product Min Qty
                if not len(row.cells)>=4 or not row.cells[3].data :
                    p_min_qty = 1.0
                else:
                    if row.cells[3].type in ['int', 'float']:
                        p_min_qty = row.cells[3].data
                    else:
                        error_list_line.append(_('Please, format the line number %s, column "Min Qty".') % (line_num,))

                #Product Unit Price
                if not len(row.cells)>=5 or not row.cells[4].data :
                    p_unit_price = 1.0
                    to_correct_ok = True
                    comment.append('Unit Price defined automatically as 1.00')
                else:
                    if row.cells[4].type in ['int', 'float']:
                        p_unit_price = row.cells[4].data
                    else:
                        error_list_line.append(_('Please, format the line number %s, column "Unit Price".') % (line_num,))

                #Product Rounding
                if not len(row.cells)>=6 or not row.cells[5].data:
                    p_rounding = False
                else:
                    if row.cells[5] and row.cells[5].type in ['int', 'float']:
                        p_rounding = row.cells[5].data
                    else:
                        error_list_line.append(_('Please, format the line number %s, column "SoQ rounding".') % (line_num,))

                #Product Min Order Qty
                if not len(row.cells)>=7 or not row.cells[6].data:
                    p_min_order_qty = 0
                else:
                    if row.cells[6].type in ['int', 'float']:
                        p_min_order_qty = row.cells[6].data
                    else:
                        error_list_line.append(_('Please, format the line number %s, column "Min Order Qty".') % (line_num,))

                #Product Comment
                if len(row.cells)>=8 and row.cells[7].data:
                    comment.append(str(row.cells[7].data))
                if comment:
                    p_comment = ', '.join(comment)

                if error_list_line:
                    error_list_line.insert(0, _('Line %s of the file was exported in the file of the lines not imported:') % (line_num,))
                    data = list(file_values[line_num].items())
                    line_with_error.append([v for k,v in sorted(data, key=lambda tup: tup[0])])
                    ignore_lines += 1
                    line_num += 1
                    error_list.append('\n -'.join(error_list_line) + '\n')
                    continue
                line_num += 1

               # [utp-746] update prices of an already product in catalog
                criteria = [
                    ('catalogue_id', '=', obj.id),
                    ('product_id', '=', default_code),
                ]
                catalog_line_id = obj_catalog_line.search(cr, uid, criteria, context=context)
                if catalog_line_id:
                    if isinstance(catalog_line_id, int):
                        catalog_line_id = [catalog_line_id]
                    # update product in catalog only if any modification
                    # and only modified fields (for sync)
                    cl_obj = obj_catalog_line.browse(cr, uid, catalog_line_id[0], context=context)
                    if cl_obj:
                        to_write = {}
                        if cl_obj.min_qty != p_min_qty:
                            to_write['min_qty'] = p_min_qty
                        if cl_obj.line_uom_id.id != uom_id:
                            to_write['line_uom_id'] = uom_id
                        if cl_obj.unit_price != p_unit_price:
                            to_write['unit_price'] = p_unit_price
                        if cl_obj.rounding != p_rounding:
                            to_write['rounding'] = p_rounding
                        if cl_obj.min_order_qty != p_min_order_qty:
                            to_write['min_order_qty'] = p_min_order_qty
                        if cl_obj.comment != p_comment:
                            to_write['comment'] = p_comment
                        if to_write:
                            vals['line_ids'].append((1, catalog_line_id[0], to_write))
                else:
                    to_write = {
                        'to_correct_ok': to_correct_ok,
                        'product_id': default_code,
                        'min_qty': p_min_qty,
                        'line_uom_id': uom_id,
                        'unit_price': p_unit_price,
                        'rounding': p_rounding,
                        'min_order_qty': p_min_order_qty,
                        'comment': p_comment,
                    }
                    vals['line_ids'].append((0, 0, to_write))

            # in case of lines ignored, we notify the user and create a file with the lines ignored
            vals.update({'text_error': _('Lines ignored: %s \n ----------------------\n') % (ignore_lines,) +
                         '\n'.join(error_list), 'data': False, 'import_error_ok': False,
                         'file_to_import': False})
            if line_with_error:
                file_to_export = self.export_file_with_error(cr, uid, ids, line_with_error=line_with_error)
                vals.update(file_to_export)
            vals['esc_update_ts'] = datetime.now().strftime(date_format)
            self.write(cr, uid, ids, vals, context=context)

            # TODO: To implement


            #res_id = self.pool.get('catalogue.import.lines').create(cr, uid, {'catalogue_id': ids[0]}, context=context)
            if any([line for line in obj.line_ids if line.to_correct_ok]) or line_with_error:
                msg_to_return = _("The import of lines had errors, please correct the red lines below")

        return self.log(cr, uid, obj.id, msg_to_return,)

    def clear_error(self, cr, uid, ids, context=None):
        '''
        Remove the error list and the file with lines in error
        '''
        vals = {'data': False, 'text_error': '', 'import_error_ok': False}
        return self.write(cr, uid, ids, vals, context=context)

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
        message = ''
        plural= ''
        for var in self.browse(cr, uid, ids, context=context):
            if var.line_ids:
                for var in var.line_ids:
                    if var.to_correct_ok:
                        line_num = var.line_number
                        if message:
                            message += ', '
                        message += str(line_num)
                        if len(message.split(',')) > 1:
                            plural = 's'
        if message:
            raise osv.except_osv(_('Warning !'), _('You need to correct the following line%s : %s')% (plural, message))
        return True

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        """[utp-746] ESC supplier catalogue default value
        and catalogue create not allowed in a not HQ instance"""
        res = super(supplier_catalogue, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        if 'partner_id' in context:
            res['is_esc'] = self._is_esc_from_partner_id(cr, uid,
                                                         context['partner_id'],
                                                         context=context)
            if res['is_esc']:
                supplier_r = self.pool.get('res.partner').read(cr, uid,
                                                               [context['partner_id']],
                                                               ['partner_type'],
                                                               context=context)
                if supplier_r and supplier_r[0] \
                   and supplier_r[0]['partner_type'] \
                   and supplier_r[0]['partner_type'] == 'esc':
                    users_obj = self.pool.get('res.users')
                    user_ids = users_obj.search(cr, uid, [('id','=', uid)],
                                                context=context)
                    if user_ids:
                        if isinstance(user_ids, int):
                            user_ids = [user_ids]
                        users = users_obj.browse(cr, uid, user_ids,
                                                 context=context)
                        if users:
                            user = users[0]
                            if user.company_id and user.company_id.instance_id:
                                if user.company_id.instance_id.level and \
                                        user.company_id.instance_id.level ==  'coordo':
                                    raise osv.except_osv(
                                        _('Error'),
                                        'For an ESC Supplier you must create the catalogue on a HQ instance.'
                                    )

                # ESC supplier catalogue: no period date
                res['period_from'] = False
                res['period_to'] = False
        return res

    def check_cat_prods_valid(self, cr, uid, cat_id, product_ids, period_from=None, period_to=None, context=None):
        '''
        Check if there is already a confirmed and active catalogue, having the same supplier, the same currency and
        with overlapping dates as a given catalogue for a list of products. Periods can be different if changed by
        on_change_period
        '''
        if not cat_id:
            raise osv.except_osv(_('Error'), _('Please give a catalogue ID to this method'))
        if context is None:
            context = {}

        products = []
        prod_cond = "cl.product_id = ocl.product_id"
        if product_ids:
            if len(product_ids) == 1:
                prod_cond = "cl.product_id = %s" % (product_ids[0],)
            else:
                prod_cond = "cl.product_id IN %s" % (tuple(product_ids),)
        ftf = ['period_from', 'period_to', 'partner_id', 'currency_id']
        cat = self.browse(cr, uid, cat_id, fields_to_fetch=ftf, context=context)
        if period_from is None:
            period_from = cat.period_from or '1970-01-01'
        elif period_from is False:
            period_from = '1970-01-01'
        if period_to is None:
            period_to = cat.period_to or '2999-12-31'
        elif period_to is False:
            period_to = '2999-12-31'

        cr.execute("""SELECT p.default_code FROM supplier_catalogue_line cl 
                LEFT JOIN supplier_catalogue c ON cl.catalogue_id = c.id
                LEFT JOIN product_product p ON cl.product_id = p.id
                , supplier_catalogue_line ocl
                LEFT JOIN supplier_catalogue oc ON ocl.catalogue_id = oc.id
            WHERE oc.id = %s AND oc.id != c.id AND c.state = 'confirmed' AND c.partner_id = %s AND c.active = 't'
                AND (COALESCE(c.period_from, '1970-01-01'), COALESCE(c.period_to, '2999-12-31')) 
                    OVERLAPS (TO_DATE(%s, 'YYYY-MM-DD'), TO_DATE(%s, 'YYYY-MM-DD'))
                AND c.currency_id = %s AND """ + prod_cond + """ GROUP BY p.default_code
        """, (cat.id, cat.partner_id.id, period_from, period_to, cat.currency_id.id)) # not_a_user_entry
        for x in cr.fetchall():
            products.append(x[0])

        return products


supplier_catalogue()


class supplier_catalogue_line(osv.osv):
    _name = 'supplier.catalogue.line'
    _rec_name = 'line_number'
    _description = 'Supplier catalogue line'
    _table = 'supplier_catalogue_line'
    # Inherits of product.product to an easier search of lines with product attributes
    _inherits = {'product.product': 'product_id'}
    _order = 'product_id, line_uom_id, min_qty'
    _trace = True

    def _create_supplier_info(self, cr, uid, vals, context=None):
        '''
        Create a pricelist line on product supplier information tab
        '''
        if context is None:
            context = {}
        supinfo_obj = self.pool.get('product.supplierinfo')
        cat_obj = self.pool.get('supplier.catalogue')
        price_obj = self.pool.get('pricelist.partnerinfo')
        prod_obj = self.pool.get('product.product')
        user_obj = self.pool.get('res.users')

        tmpl_id = prod_obj.browse(cr, uid, vals['product_id'], context=context).product_tmpl_id.id
        catalogue = cat_obj.browse(cr, uid, vals['catalogue_id'], context=context)

        if catalogue.partner_id.id == user_obj.browse(cr, uid, uid, context=context).company_id.partner_id.id:
            return vals

        # Search if a product_supplierinfo exists for the catalogue, if not, create it
        sup_ids = supinfo_obj.search(cr, uid, [('product_id', '=', tmpl_id),
                                               ('catalogue_id', '=', vals['catalogue_id'])],
                                     context=context)
        sup_id = sup_ids and sup_ids[0] or False
        if not sup_id:
            sup_id = supinfo_obj.create(cr, uid, {'name': catalogue.partner_id.id,
                                                  'sequence': 0,
                                                  'delay': catalogue.partner_id.default_delay,
                                                  'product_id': tmpl_id,
                                                  'product_code': vals.get('product_code', False),
                                                  'catalogue_id': vals['catalogue_id'],
                                                  },
                                        context=context)
        else:
            supinfo_obj.write(cr, uid, [sup_id], {'product_code': vals.get('product_code', False)}, context=context)

        # Pass 'no_store_function' to False to compute the sequence on the pricelist.partnerinfo object
        create_context = context.copy()
        if context.get('no_store_function'):
            create_context['no_store_function'] = False

        price_id = price_obj.create(cr, uid, {'name': catalogue.name,
                                              'suppinfo_id': sup_id,
                                              'min_quantity': vals.get('min_qty', 0.00),
                                              'uom_id': vals['line_uom_id'],
                                              'price': vals['unit_price'],
                                              'rounding': vals.get('rounding', 1.00),
                                              'min_order_qty': vals.get('min_order_qty', 0.00),
                                              'currency_id': catalogue.currency_id.id,
                                              'valid_from': catalogue.period_from,
                                              'valid_till': catalogue.period_to,},
                                    context=create_context)

        vals.update({'supplier_info_id': sup_id,
                     'partner_info_id': price_id})

        return vals

    def create(self, cr, uid, vals, context=None):
        '''
        Create a pricelist line on product supplier information tab
        '''
        cat_obj = self.pool.get('supplier.catalogue')
        catalogue = False
        if vals.get('catalogue_id'):
            catalogue = cat_obj.read(cr, uid, vals['catalogue_id'], ['state', 'active', 'from_sync'], context=context)

        if catalogue:
            if catalogue['from_sync'] and not context.get('sync_update_execution'):
                raise osv.except_osv(_('Error'), _('You can not add a line to a catalogue created from sync'))
            if catalogue['state'] != 'draft':
                vals = self._create_supplier_info(cr, uid, vals, context=context)

        ids = super(supplier_catalogue_line, self).create(cr, uid, vals, context=context)

        # US-12606: Check if the product exists in another valid catalogue
        if vals.get('product_id') and catalogue and catalogue['state'] == 'confirmed' and catalogue['active']:
            invalid_prod = cat_obj.check_cat_prods_valid(cr, uid, vals['catalogue_id'], [vals['product_id']], None,
                                                         None, context=context)
            if invalid_prod:
                raise osv.except_osv(_('Warning!'),
                                     _('This catalogue line contains the product %s which is a duplicate in another catalogue for the same supplier! Please remove the product from this/other catalogue before saving')
                                     % (invalid_prod[0],))

        self._check_min_quantity(cr, uid, ids, context=context)

        return ids

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update the pricelist line on product supplier information tab
        '''
        if not ids:
            return True
        if context is None:
            context = {}

        #product_obj = self.pool.get('product.product')
        #uom_obj = self.pool.get('product.uom')
        cat_obj = self.pool.get('supplier.catalogue')
        obj_data = self.pool.get('ir.model.data')
        uom_id = obj_data.get_object_reference(cr, uid, 'msf_doc_import','uom_tbd')[1]
        prod_id = obj_data.get_object_reference(cr, uid, 'msf_doc_import','product_tbd')[1]

        for line in self.browse(cr, uid, ids, context=context):
            if line.catalogue_id.from_sync and not context.get('sync_update_execution'):
                raise osv.except_osv(_('Error'), _('You can not modify lines from a catalogue created from sync'))
            new_vals = vals.copy()
            cat_state = cat_obj.read(cr, uid, new_vals.get('catalogue_id', line.catalogue_id.id), ['state'], context=context)['state']
            if 'product_id' in new_vals and 'line_uom_id' in new_vals and new_vals['product_id'] != prod_id and new_vals['line_uom_id'] != uom_id:
                new_vals['to_correct_ok'] = False
            # If product is changed
            if cat_state != 'draft' and new_vals.get('product_id', line.product_id.id) != line.product_id.id:
                c = context.copy()
                c.update({'product_change': True})
                # Remove the old pricelist.partnerinfo and create a new one
                if line.partner_info_id:
                    self.pool.get('pricelist.partnerinfo').unlink(cr, uid, line.partner_info_id.id, context=c)

                # Check if the removed line wasn't the last line of the supplierinfo
                if line.supplier_info_id and len(line.supplier_info_id.pricelist_ids) == 0:
                    # Remove the supplier info
                    self.pool.get('product.supplierinfo').unlink(cr, uid, line.supplier_info_id.id, context=c)

                # Create new partnerinfo line
                new_vals.update({'catalogue_id': new_vals.get('catalogue_id', line.catalogue_id.id),
                                 'product_id': new_vals.get('product_id', line.product_id.id),
                                 'product_code': new_vals.get('product_code', line.product_code),
                                 'min_qty': new_vals.get('min_qty', line.min_qty),
                                 'line_uom_id': new_vals.get('line_uom_id', line.line_uom_id.id),
                                 'unit_price': new_vals.get('unit_price', line.unit_price),
                                 'rounding': new_vals.get('rounding', line.rounding),
                                 'min_order_qty': new_vals.get('min_order_qty', line.min_order_qty),
                                 'comment': new_vals.get('comment', line.comment),
                                 })
                new_vals = self._create_supplier_info(cr, uid, new_vals, context=context)
            elif cat_state != 'draft' and line.partner_info_id:
                pinfo_data = {'min_quantity': new_vals.get('min_qty', line.min_qty),
                              'price': new_vals.get('unit_price', line.unit_price),
                              'uom_id': new_vals.get('line_uom_id', line.line_uom_id.id),
                              'rounding': new_vals.get('rounding', line.rounding),
                              'min_order_qty': new_vals.get('min_order_qty', line.min_order_qty)
                              }
                # Update the pricelist line on product supplier information tab
                if 'product_code' in new_vals and line.partner_info_id.suppinfo_id.product_code != new_vals['product_code']:
                    self.pool.get('product.supplierinfo').write(cr, uid, [line.partner_info_id.suppinfo_id.id], {'product_code': new_vals['product_code']})
                self.pool.get('pricelist.partnerinfo').write(cr, uid, [line.partner_info_id.id],
                                                             pinfo_data, context=context)
            elif cat_state != 'draft':
                new_vals.update({'catalogue_id': new_vals.get('catalogue_id', line.catalogue_id.id),
                                 'product_id': new_vals.get('product_id', line.product_id.id),
                                 'product_code': new_vals.get('product_code', line.product_code),
                                 'min_qty': new_vals.get('min_qty', line.min_qty),
                                 'line_uom_id': new_vals.get('line_uom_id', line.line_uom_id.id),
                                 'unit_price': new_vals.get('unit_price', line.unit_price),
                                 'rounding': new_vals.get('rounding', line.rounding),
                                 'min_order_qty': new_vals.get('min_order_qty', line.min_order_qty),})
                new_vals = self._create_supplier_info(cr, uid, new_vals, context=context)
            elif cat_state == 'draft':
                #utp1033
                cr.execute('''delete from pricelist_partnerinfo
                              where id in (select partner_info_id
                                          from supplier_catalogue_line
                                          where catalogue_id = %s)''', (ids[0],))
                cr.execute('''delete from product_supplierinfo
                              where id in (select supplier_info_id
                                          from supplier_catalogue_line
                                          where catalogue_id = %s)
                              and id not in (select suppinfo_id from
                                            pricelist_partnerinfo ) ''',
                           (ids[0],))

            res = super(supplier_catalogue_line, self).write(cr, uid, [line.id], new_vals, context=context)

        self._check_min_quantity(cr, uid, ids, context=context)

        return res

    def unlink(self, cr, uid, ids, context=None):
        '''
        Remove the pricelist line on product supplier information tab
        If the product supplier information has no line, remove it
        '''
        if isinstance(ids, int):
            ids = [ids]

        # forbid supplier catalogue line coming from higher instance level to be manually deleted:
        to_unlink = set()
        for cat_line in self.browse(cr, uid, ids, fields_to_fetch=['catalogue_id'], context=context):
            if not cat_line.catalogue_id.from_sync or context.get('sync_update_execution', False):
                to_unlink.add(cat_line.id)
            else:
                raise osv.except_osv(
                    _('Error'),
                    _('Warning! You cannot delete a synched supplier catalogue line created in a higher instance level.')
                )
        to_unlink = list(to_unlink)

        for line in self.browse(cr, uid, to_unlink, context=context):
            c = context is not None and context.copy() or {}
            c.update({'product_change': True})
            # Remove the pricelist line in product tab
            if line.partner_info_id:
                self.pool.get('pricelist.partnerinfo').unlink(cr, uid, line.partner_info_id.id, context=c)

            # Check if the removed line wasn't the last line of the supplierinfo
            if line.supplier_info_id and len(line.supplier_info_id.pricelist_ids) == 0:
                # Remove the supplier info
                self.pool.get('product.supplierinfo').unlink(cr, uid, line.supplier_info_id.id, context=c)

        return super(supplier_catalogue_line, self).unlink(cr, uid, to_unlink, context=context)

    def _check_min_quantity(self, cr, uid, ids, context=None):
        '''
        Check if the min_qty field is set
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        if not context.get('noraise'):
            read_result = self.read(cr, uid, ids, ['min_qty'],
                                    context=context)
            negative_qty = [x['id'] for x in read_result if x['min_qty'] <= 0.00]
            if negative_qty:
                line = self.browse(cr, uid, negative_qty[0], context=context)
                raise osv.except_osv(_('Error'), _('The line of product [%s] %s has a negative or zero min. qty !') % (line.product_id.default_code, line.product_id.name))

        return True

    _columns = {
        'line_number': fields.integer(string='Line'),
        'catalogue_id': fields.many2one('supplier.catalogue', string='Catalogue', required=True, ondelete='cascade'),
        'product_code': fields.char('Supplier Code', size=64),
        'product_id': fields.many2one('product.product', string='Product', required=True, ondelete='cascade'),
        'min_qty': fields.float(digits=(16,2), string='Min. Qty', required=True,
                                help='Minimal order quantity to get this unit price.', related_uom='line_uom_id'),
        'line_uom_id': fields.many2one('product.uom', string='Product UoM', required=True,
                                       help='UoM of the product used to get this unit price.'),
        'unit_price': fields.float(string='Unit Price', required=True, digits_compute=dp.get_precision('Purchase Price Computation')),
        'rounding': fields.float(digits=(16,2), string='SoQ rounding',
                                 help='The ordered quantity must be a multiple of this rounding value.', related_uom='line_uom_id'),
        'min_order_qty': fields.float(digits=(16,2), string='Min. Order Qty', related_uom='line_uom_id'),
        'comment': fields.char(size=64, string='Comment'),
        'supplier_info_id': fields.many2one('product.supplierinfo', string='Linked Supplier Info'),
        'partner_info_id': fields.many2one('pricelist.partnerinfo', string='Linked Supplier Info line'),
        'to_correct_ok': fields.boolean('To correct'),
        'mml_status': fields.function(_get_std_mml_status, method=True, type='selection', selection=[('T', 'Yes'), ('F', 'No'), ('na', '')], string='MML', multi='mml'),
        'msl_status': fields.function(_get_std_mml_status, method=True, type='selection', selection=[('T', 'Yes'), ('F', 'No'), ('na', '')], string='MSL', multi='mml'),
    }

    _defaults = {
        'rounding': 1.00,
        'mml_status': 'na',
        'msl_status': 'na',
    }

    def product_change(self, cr, uid, ids, product_id, min_qty, min_order_qty, catalogue_id, context=None):
        '''
        When the product change, fill automatically the line_uom_id field of the
        catalogue line.
        @param product_id: ID of the selected product or False
        '''
        cat_obj = self.pool.get('supplier.catalogue')
        v = {'line_uom_id': False}
        res = {}

        if product_id:
            # US-12606: Check if the product exists in another valid catalogue
            if catalogue_id:
                catalogue = cat_obj.read(cr, uid, catalogue_id, ['state', 'active'], context=context)
                if catalogue['state'] == 'confirmed' and catalogue['active']:
                    invalid_prod = cat_obj.check_cat_prods_valid(cr, uid, catalogue_id, [product_id], None, None, context=context)
                    if invalid_prod:
                        return {
                            'value': {'product_id': False},
                            'warning': {'title': _('Warning!'), 'message':
                                        _('This catalogue line contains the product %s which is a duplicate in another catalogue for the same supplier! Please remove the product from this/other catalogue before saving')
                                        % (invalid_prod[0],)}
                        }

            product = self.pool.get('product.product').read(cr, uid, product_id, ['uom_id'], context=context)
            v.update({'line_uom_id': product['uom_id'][0]})
            res = self.change_uom_qty(cr, uid, ids, product['uom_id'][0], min_qty, min_order_qty)
        else:
            return {}

        res.setdefault('value', {}).update(v)

        return res

    def change_uom_qty(self, cr, uid, ids, uom_id, min_qty, min_order_qty, rounding=True):
        '''
        Check round qty according to UoM
        '''
        res = {}
        uom_obj = self.pool.get('product.uom')

        if min_qty:
            res = uom_obj._change_round_up_qty(cr, uid, uom_id, min_qty, 'min_qty', result=res)

        if min_order_qty:
            res = uom_obj._change_round_up_qty(cr, uid, uom_id, min_order_qty, 'min_order_qty', result=res)

        if rounding:
            res.setdefault('value', {})
            res['value']['rounding'] = 0.00

        return res

    def change_soq_quantity(self, cr, uid, ids, soq, uom_id, context=None):
        """
        When the SoQ quantity is changed, check if the new quantity is consistent
        with rounding value of the UoM of the catalogue line.
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of product.product on which the SoQ quantity is changed
        :param soq: New value for SoQ Quantity
        :param uom_id: ID of the product.uom linked to the product
        :param context: Context of the call
        :return: A dictionary that contains a warning message and the SoQ quantity
        rounded with the UoM rounding value
        """
        res = self.pool.get('product.product').change_soq_quantity(cr, uid, [], soq, uom_id, context=context)

        if res.get('value', {}).get('soq_quantity', False):
            res['value']['rounding'] = res['value'].pop('soq_quantity')

        return res

    def onChangeSearchNomenclature(self, cr, uid, line_id, position, line_type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        '''
        Method to fill nomenclature fields in search view
        '''
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, [], position, line_type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=num, context=context)

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Override the tree view to display historical prices according to context
        '''
        if context is None:
            context = {}
        res = super(supplier_catalogue_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

        # If the context is set to open historical view
        if context.get('catalogue_ids', False) and view_type == 'tree':
            catalogues = self.pool.get('supplier.catalogue').browse(cr, uid, context.get('catalogue_ids'), context=context)

            # Modify the tree view to add one column by pricelist
            line_view = """<tree string="Historical prices" editable="top" noteditable="1" notselectable="0"
                    hide_new_button="1" hide_delete_button="1">
                   <field name="product_id"/>
                   <field name="line_uom_id" />
                   <field name="min_qty" />"""

            for cat in catalogues:
                line_view += """<field name="%s" />""" % cat.period_from

            line_view += "</tree>"

            if res['type'] == 'tree':
                res['arch'] = line_view

        return res

    def fields_get(self, cr, uid, fields=None, context=None, with_uom_rounding=False):
        '''
        Override the fields to display historical prices according to context
        '''
        if context is None:
            context = {}
        res = super(supplier_catalogue_line, self).fields_get(cr, uid, fields, context)

        if context.get('catalogue_ids', False):
            catalogues = self.pool.get('supplier.catalogue').browse(cr, uid, context.get('catalogue_ids'), context=context)
            for cat in catalogues:
                cat_from = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=cat.period_from, context=context)
                cat_to = ''
                if cat.period_to:
                    cat_to = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=cat.period_to, context=context)
                res.update({cat.period_from: {'size': 64,
                                              'selectable': True,
                                              'string': '%s-%s' % (cat_from, cat_to),
                                              'type': 'char',}})

        return res

    def read(self, cr, uid, ids, fields=None, context=None, load="_classic_write"):
        if context is None:
            context = {}
        if context.get('catalogue_ids', False):
            line_dict = {}
            new_context = context.copy()
            new_context.pop('catalogue_ids')
            catalogues = self.pool.get('supplier.catalogue').browse(cr, uid, context.get('catalogue_ids'), context=new_context)
            for cat in catalogues:
                period_name = '%s' % cat.period_from
                for line in cat.line_ids:
                    line_name = '%s_%s_%s' % (line.product_id.id, line.min_qty, line.line_uom_id.id)
                    if line_name not in line_dict:
                        line_dict.update({line_name: {}})

                    line_dict[line_name].update({period_name: '%s' % line.unit_price})

            res = super(supplier_catalogue_line, self).read(cr, uid, ids, fields, context=context)

            for r in res:
                line_name = '%s_%s_%s' % (r['product_id'][0], r['min_qty'], r['line_uom_id'][0])
                for period in line_dict[line_name]:
                    r.update({period: line_dict[line_name][period]})

        else:
            res = super(supplier_catalogue_line, self).read(cr, uid, ids, fields, context=context)

        return res


supplier_catalogue_line()


class supplier_historical_catalogue(osv.osv_memory):
    _name = 'supplier.historical.catalogue'

    _columns = {
        'partner_id': fields.many2one('res.partner', string='Supplier'),
        'currency_id': fields.many2one('res.currency', string='Currency', required=True),
        'from_date': fields.date(string='From', required=True),
        'to_date': fields.date(string='To', required=True),
    }

    _defaults = {
        'partner_id': lambda obj, uid, ids, ctx: ctx.get('active_id'),
        'to_date': lambda *a: time.strftime('%Y-%m-%d'),
    }

    def open_historical_prices(self, cr, uid, ids, context=None):
        '''
        Open the historical prices view
        '''
        if not context:
            context = {}

        for hist in self.browse(cr, uid, ids, context=context):
            catalogue_ids = self.pool.get('supplier.catalogue').search(cr, uid, [('partner_id', '=', hist.partner_id.id),
                                                                                 ('active', 'in', ['t', 'f']),
                                                                                 ('currency_id', '=', hist.currency_id.id),
                                                                                 ('period_from', '<=', hist.to_date),
                                                                                 '|', ('period_to', '=', False),
                                                                                 ('period_to', '>=', hist.from_date)])

            if not catalogue_ids:
                raise osv.except_osv(_('Error'), _('No catalogues found for this supplier and this currency in the period !'))

            line_dict = {}
            line_ids = []
            catalogues = self.pool.get('supplier.catalogue').browse(cr, uid, catalogue_ids, context=context)
            for cat in catalogues:
                for line in cat.line_ids:
                    line_name = '%s_%s_%s' % (line.product_id.id, line.min_qty, line.line_uom_id.id)
                    if line_name not in line_dict:
                        line_dict.update({line_name: {}})
                        line_ids.append(line.id)

            context.update({'from_date': hist.from_date,
                            'to_date': hist.to_date,
                            'partner_id': hist.partner_id.id,
                            'currency_id': hist.currency_id.id,
                            'catalogue_ids': catalogue_ids})

        from_str = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=context.get('from_date'), context=context)
        to_str = self.pool.get('date.tools').get_date_formatted(cr, uid, d_type='date', datetime=context.get('to_date'), context=context)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'supplier_catalogue', 'non_edit_supplier_catalogue_line_tree_view')[1]

        return {'type': 'ir.actions.act_window',
                'name': '%s - Historical prices (%s) - from %s to %s' % (hist.partner_id.name, hist.currency_id.name, from_str, to_str),
                'res_model': 'supplier.catalogue.line',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', line_ids)],
                'view_id': [view_id],
                'context': context}

supplier_historical_catalogue()


class from_supplier_choose_catalogue(osv.osv_memory):
    _name = 'from.supplier.choose.catalogue'

    _columns = {
        'partner_id': fields.many2one('res.partner', string='Supplier', required=True),
        'catalogue_id': fields.many2one('supplier.catalogue', string='Catalogue', required=True),
    }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        '''
        Fill partner_id from context
        '''
        if context is None:
            context = {}
        if not context.get('active_id', False):
            raise osv.except_osv(_('Error'), _('No catalogue found !'))

        partner_id = context.get('active_id')

        if not self.pool.get('supplier.catalogue').search(cr, uid,
                                                          [('partner_id', '=', partner_id)],
                                                          limit=1, context=context, order='NO_ORDER'):
            raise osv.except_osv(_('Error'), _('No catalogue found !'))

        res = super(from_supplier_choose_catalogue, self).default_get(cr, uid, fields, context=context, from_web=from_web)

        res.update({'partner_id': partner_id})

        return res

    def open_catalogue(self, cr, uid, ids, context=None):
        '''
        Open catalogue lines
        '''
        wiz = self.browse(cr, uid, ids[0], context=context)

        return self.pool.get('supplier.catalogue').open_lines(cr, uid, wiz.catalogue_id.id, context=context)

from_supplier_choose_catalogue()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
