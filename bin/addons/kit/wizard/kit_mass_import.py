# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Copyright (C) 2011 MSF, TeMPO Consulting.
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

# External libraries imports
import time
import base64

# Server imports
from osv import osv
from osv import fields
from tools.translate import _

# Addons imports
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML


class kit_mass_import(osv.osv):
    _name = 'kit.mass.import'

    _columns = {
        'name': fields.datetime(
            string='Name',
            required=True,
        ),
        'file_to_import': fields.binary(
            string='File to import',
            required=False,
            readonly=True,
            states={
                'draft': [
                    ('readonly', False),
                ],
                'check_error': [
                    ('readonly', False),
                ],
            },
        ),
        'filename': fields.char(
            size=128,
            string='Filename',
        ),
        'template_file': fields.binary(
            string='Template file',
            readonly=True,
        ),
        'template_filename': fields.char(
            size=128,
            string='Template filename',
        ),
        'state': fields.selection(
            selection=[
                ('draft', 'Not started'),
                ('check_in_progress', 'Check consistency'),
                ('check_done', 'Consistency OK'),
                ('check_error', 'Error on consistency check'),
                ('import_in_progress', 'Import in progress'),
                ('complete', 'Complete'),
            ],
            string='State',
            readonly=True,
        ),
        'warning_message': fields.text(
            string='Warning message',
            readonly=True,
        ),
        'display_warning_message': fields.boolean(
            string='Display warning message',
        ),
        'error_message': fields.text(
            string='Error message',
            readonly=True,
        ),
        'display_error_message': fields.boolean(
            string='Display error message',
        ),
        'warning_import': fields.text(
            string='Warning message',
            readonly=True,
        ),
        'error_import': fields.text(
            string='Error message',
            readonly=True,
        ),
        'log_import': fields.text(
            string='Import log',
            readonly=True,
        ),
    }

    _defaults = {
        'name': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'state': lambda *a: 'draft',
    }

    def get_template(self, cr, uid, ids, context=None):
        """
        Send a empty template file to the user
        """
        if context is None:
            context = {}

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'kit_mass_import_export',
            'datas': {'target_filename': _('Theoretical Kit Template')},
            'context': context,
        }

    def get_value_from_excel(self, cr, uid, file_to_import, context=None):
        """
        Parse the Excel XML Spreadsheet to get the value of the Theoretical
        Kit Items.

        Columns of the file must be like that:
          #1: Kit Code (mandatory)
          #2: Kit Description (not used for import)
          #3: Kit Version (mandatory)
          #4: Active (True or False)
          #5: Module
          #6: Product Code (mandatory)
          #7: Product Description (not used for import)
          #8: Product Qty (mandatory)
          #9: Product UoM (if not set, take the Product Default UoM)
        """
        if context is None:
            context = {}

        values = {}
        # Read the XML file
        xml_file = base64.b64decode(file_to_import)
        fileobj = SpreadsheetXML(xmlstring=xml_file)

        # Read all lines
        rows = fileobj.getRows()

        # Get value for each lines
        index = 0
        for r in rows:
            if not index:
                index += 1
                continue
            index += 1
            values.setdefault(index, [])
            for cell_nb in range(len(r)):
                cell_data = r.cells and r.cells[cell_nb] and\
                    r.cells[cell_nb].data
                values[index].append(cell_data)

        return values

    def import_data_from_file(self, cr, uid, ids, context=None, force=False):
        """
        Read the file given by the user in the wizard and create the
        associated Theoretical Kit.
        """
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        tkc_values = {}
        active_values = [True, 'True', 'TRUE']
        for wiz in self.browse(cr, uid, ids, context=context):
            if not wiz.file_to_import:
                raise osv.except_osv(
                    _('Error'),
                    _('No file to import'),
                )
            # Get values from file
            values = self.get_value_from_excel(
                cr, uid, wiz.file_to_import, context=context)
            self.write(cr, uid, [wiz.id], {
                'state': 'check_in_progress',
            }, context=context)
            if self._chk_consistency(
                    cr, uid, wiz.id, values, context=context, force=force):
                self.write(cr, uid, [wiz.id], {
                    'state': 'check_done',
                }, context=context)
                """
                Create a dictionnary with all lines with the kit code + version
                as key and the list of items as value.
                  #1: Kit Code (mandatory)
                  #2: Kit Description (not used for import)
                  #3: Kit Version (mandatory)
                  #4: Active (True or False)
                  #5: Module
                  #6: Product Code (mandatory)
                  #7: Product Description (not used for import)
                  #8: Product Qty (mandatory)
                  #9: Product UoM (if not set, take the Product Default UoM)
                  #10: Product Comments
                """
                for line, val in values.items():
                    vval = val[3]
                    if isinstance(val[3], str):
                        vval = val[3].strip()
                    kit_key = '%s_%s' % (val[0], val[2])
                    tkc_values.setdefault(kit_key, {
                        'code': val[0],
                        'version': val[2],
                        'active': vval in active_values and True or False,
                        'items': [],
                    })
                    tkc_values[kit_key]['items'].append({
                        'line': line,
                        'module': val[4],
                        'item': val[5],
                        'qty': val[7],
                        'uom': val[8],
                        'comment': val[9],
                    })
                self.import_kits(cr, uid, wiz, tkc_values, context=context)
            else:
                self.write(cr, uid, [wiz.id], {
                    'state': 'check_error',
                }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form,tree',
            'context': context,
            'target': 'same',
        }

    def force_import_data(self, cr, uid, ids, context=None):
        """
        If warning messages are displayed, the user can force the import
        """
        return self.\
            import_data_from_file(cr, uid, ids, context=context, force=True)

    def _chk_consistency(self, cr, uid, wizard_id,
                         values=None, context=None, force=False):
        """
        Check if all lines of the file have the mandatory field set and values
        consistent for other fields.
        """
        if context is None:
            context = {}

        warning_msg = {}
        warning_index = set()
        error_msg = {}
        error_index = set()
        for line, val in values.items():
            if not val or len(val) < 8:
                error_index.add(line)
                error_msg.setdefault(line, [])
                error_msg[line].append(
                    _('The line must have at least 8 columns')
                )
                continue

            # Col. #1 :: Kit Code mandatory
            if not val[0]:
                error_index.add(line)
                error_msg.setdefault(line, [])
                error_msg[line].append(
                    _('Column 1 :: \'Kit Code\' must be set')
                )

            # Col. 3 :: Kit Version mandatory
            if not val[2]:
                error_index.add(line)
                error_msg.setdefault(line, [])
                error_msg[line].append(
                    _('Column 3 :: \'Version\' must be set')
                )

            # Col. 4 :: Active (expected values: True or False)a
            active_values = [True, False, 'True', 'False', 'TRUE', 'FALSE']
            vval = val[3]
            if isinstance(vval, str):
                vval = vval.strip()
            if not vval or vval not in active_values:
                warning_index.add(line)
                warning_msg.setdefault(line, [])
                warning_msg[line].append(
                    _('Column 4 :: \'Active\' must be \'True\' or \'False\' '\
                      '- Forced to \'True\'')
                )

            # Col. 6 :: Product Code mandatory
            if not val[5]:
                error_index.add(line)
                error_msg.setdefault(line, [])
                error_msg[line].append(
                    _('Column 6 :: \'Product Code\' must be set')
                )

            # Col. 8 :: Product Qty mandatory
            try:
                msg = []
                if not val[7] or float(val[7]) <= 0.00:
                    msg = _('Column 8 :: \'Product Qty\' must be positive')
            except ValueError:
                msg = _('Column 8 :: \'Product Qty\' must be a float value')
            finally:
                if msg:
                    error_index.add(line)
                    error_msg.setdefault(line, [])
                    error_msg[line].append(msg)

            # Col. 9 :: Product UoM (set as Product default UoM is empty)
            if len(val) < 9 or not val[8]:
                warning_index.add(line)
                warning_msg.setdefault(line, [])
                warning_msg[line].append(
                    _('Column 9 :: \'Product UoM\' is not set - Forced to '\
                      'the default UoM of the product')
                )

        # Generation of the warning message
        warn_text = self._generate_message(warning_msg, list(warning_index))
        # Generation of the error message
        error_text = self._generate_message(error_msg, list(error_index))

        if warn_text or error_text:
            self.write(cr, uid, wizard_id, {
                'warning_message': warn_text,
                'display_warning_message': warn_text and True or False,
                'error_message': error_text,
                'display_error_message': error_text and True or False,
            }, context=context)

            # In case on only warning message and user forces the import
            if force and not error_text:
                return True

            return False
        else:
            self.write(cr, uid, wizard_id, {
                'warning_message': '',
                'display_warning_message': False,
                'error_message': '',
                'display_error_message': False,
            }, context=context)


        return True

    def import_kits(self, cr, uid, wizard, kit_values={}, context=None):
        """
        Import the Kits and their items according to data in kit_values.
        kit_values is a dict the concatenation of kit product code and kit
        version as key. E.g:
        kit_values = {
            'KMEDOK25PE_1.0.0': {
                'code': 'KMEDOK25PE',
                'version': '1.0.0',
                'active': True,
                'items': [
                    {
                        'line': 1,
                        'module': 'module 1',
                        'item': 'ADAPCABL1S-',
                        'qty': 20.0,
                        'uom': 'PCE',
                        'comment': 'Test',
                    },
                    {
                        'line': 2,
                        'module': 'module 1',
                        'item': 'ADAPCABL2S-',
                        'qty': 10.0,
                        'uom': False,
                        'comment': '',
                    }
                ],
            }
        }
        """
        kit_obj = self.pool.get('composition.kit')
        item_obj = self.pool.get('composition.item')

        if context is None:
            context = {}

        if not kit_values:
            self.write(cr, uid, wizard.id, {
                'error_message': _('No data to import'),
                'display_error_message': True,
                'state': 'check_error',
            }, context=context)
            return True

        cache_product = {}
        cache_uom = {}

        warning_index = set()
        warning_msg = {}
        error_index = set()
        error_msg = {}
        log_msg = []

        for values in kit_values.values():
            warning = False
            # Create the Theoretical Kit
            kit_product_id = self._get_product(
                cr, uid, values.get('code'), cache_product, check_kit=True)

            # Manage product not found or product is not a kit
            if not kit_product_id or kit_product_id < 0:
                err_index = values['items'][0]['line']
                error_index.add(err_index)
                error_msg.setdefault(err_index, [])
                if not kit_product_id:
                    error_msg[err_index].append(
                        _('Kit Product \'%s\' not found in the database - '\
                          'Kit not imported') %
                        values.get('code')
                    )
                elif kit_product_id < 0:
                    error_msg[err_index].append(
                        _('Kit Product \'%s\' is not a kit product - '\
                          'Kit not imported') %
                        values.get('code')
                    )
                continue

            # Check if kit exist for this product
            update_kit_id = False
            exist_kit_ids = kit_obj.search(cr, uid, [
                ('composition_product_id', '=', kit_product_id),
                ('composition_version_txt', '=', values.get('version')),
                ('composition_type', '=', 'theoretical'),
                ('active', 'in', ['t', 'f']),
            ], context=context)
            if exist_kit_ids:
                for exist_kit in kit_obj.browse(
                        cr, uid, exist_kit_ids, context=context):
                    if exist_kit.state == 'draft':
                        update_kit_id = exist_kit.id
                        break
                    else:
                        err_index = values['items'][0]['line']
                        error_index.add(err_index)
                        error_msg.setdefault(err_index, [])
                        error_msg[err_index].append(
                            _("""A kit already exists for the Kit Product
'\'%s\'. But this kit is not in \'Draft\' state""") % values.get('code')
                        )
                else:
                    # In case of non draft existing kit, pass to the next kit
                    continue

            kit_values = {
                'composition_type': 'theoretical',
                'composition_product_id': kit_product_id,
                'composition_version_txt': values.get('version'),
                'active': values.get('active'),
            }
            items = []

            # Creation of items
            for item in values.get('items'):
                item_product_id = self._get_product(
                    cr, uid, item.get('item'), cache_product)
                if not item_product_id:
                    err_index = item.get('line')
                    error_index.add(err_index)
                    error_msg.setdefault(err_index, [])
                    error_msg[err_index].append(
                        _('Product \'%s\' not found in the database - '\
                          'Complete kit \'%s\' not imported') % (
                            item.get('item'),
                            values.get('code'),
                        )
                    )
                    break

                item_uom_id = None
                if item.get('uom'):
                    item_uom_id = self._get_uom(
                        cr, uid, item.get('uom'), cache_uom)
                    if not item_uom_id:
                        warning = True
                        warn_index = item.get('line')
                        warning_index.add(warn_index)
                        warning_msg.setdefault(warn_index, [])
                        warning_msg[warn_index].append(
                            _('The UoM \'%s\' not found in the database. '\
                              'Forced to product default UoM') %
                            item.get('uom')
                        )
                else:
                    warning = True
                    warn_index = item.get('line')
                    warning_index.add(warn_index)
                    warning_msg.setdefault(warn_index, [])
                    warning_msg[warn_index].append(
                        _('UoM not set in file. Forced to product default UoM')
                    )

                if not item_uom_id:
                    item_uom_id = self._get_uom_from_product(
                        cr, uid, item_product_id, context=context)

                update_item_id = False
                if update_kit_id:
                    exist_item_ids = item_obj.search(cr, uid, [
                        ('item_module', '=', item.get('module', False)),
                        ('item_product_id', '=', item_product_id),
                        ('item_kit_id', '=', update_kit_id),
                    ], context=context)
                    if exist_item_ids:
                        update_item_id = exist_item_ids[0]

                items.append({
                    'to_update': update_item_id,
                    'item_module': item.get('module', False),
                    'item_product_id': item_product_id,
                    'item_qty': item.get('qty', 0.00),
                    'item_uom_id': item_uom_id,
                    'comment': item.get('comment', ''),
                })
            else:
                if update_kit_id:
                    kit_id = update_kit_id
                    kit_obj.write(cr, uid, update_kit_id,kit_values, context)
                    msg = _('Kit \'%s\' updated') % values.get('code')
                else:
                    kit_id = kit_obj.\
                        create(cr, uid, kit_values, context=context)
                    msg = _('Kit \'%s\' created') % values.get('code')

                if warning:
                    msg += _(' with warning')
                log_msg.append(msg)

                updated_items = []
                for i_vals in items:
                    i_vals['item_kit_id'] = kit_id
                    if i_vals['to_update']:
                        it_id = i_vals['to_update']
                        updated_items.append(it_id)
                        item_obj.write(cr, uid, it_id, i_vals, context=context)
                    else:
                        updated_items.append(
                            item_obj.create(cr, uid, i_vals, context=context)
                        )

                # Delete old kit items in case of update
                if update_kit_id:
                    old_items = item_obj.search(cr, uid, [
                        ('item_kit_id', '=', update_kit_id),
                        ('id', 'not in', updated_items),
                    ], context=context)
                    for it in item_obj.browse(cr, uid, old_items, context):
                        warning = True
                        warn_index = 0
                        warning_index.add(warn_index)
                        warning_msg.setdefault(warn_index, [])
                        warning_msg[warn_index].append(_(
                            """Kit \'%s\' - Module \'%s\' - Item \'%s\' not found in file, item removed"""
                        ) % (
                            it.item_kit_id.composition_product_id.default_code,
                            it.item_module or '',
                            it.item_product_id.default_code,
                        ))
                    item_obj.unlink(cr, uid, old_items, context=context)

        # Generation of the warning message
        warn_text = self._generate_message(warning_msg, list(warning_index))
        # Generation of the error message
        error_text = self._generate_message(error_msg, list(error_index))
        # Generation of log message
        log_text = self._generate_message(log_msg)

        self.write(cr, uid, wizard.id, {
            'state': 'complete',
            'log_import': log_text,
            'display_warning_message': warn_text and True or False,
            'display_error_message': error_text and True or False,
            'warning_import': warn_text,
            'error_import': error_text,
        }, context=context)

        return True

    def _get_record(self, cr, uid, field, value, model, cache=None):
        """
        Search in cache or fill the cache with the ID of the db.
        """
        if cache is None:
            cache = {}

        if value not in cache:
            record_ids = self.pool.get(model).search(cr, uid, [(field, '=ilike', value)])
            if record_ids:
                cache[value] = record_ids[0]
            else:
                cache[value] = False

        return cache[value]

    def _get_product(self, cr, uid, code, cache=None, check_kit=False):
        """
        Get the product in cache or in DB. In case of the product is not
        in cache, put it in cache.
        """
        kit_product_id = self._get_record(
            cr, uid, 'default_code', code, 'product.product', cache)

        # Check if the product is a Kit
        if kit_product_id and check_kit:
            is_kit = self.pool.get('product.product').\
                read(cr, uid, kit_product_id, ['subtype'])['subtype'] == 'kit'
            if not is_kit:
                return -1

        return kit_product_id

    def _get_uom(self, cr, uid, name, cache=None):
        """
        Get the UoM in cache or in DB. In case of the UoM is not in cache,
        put it in cache.
        """
        return self._get_record(
            cr, uid, 'name', name, 'product.uom', cache)

    def _get_uom_from_product(self, cr, uid, product_id, context=None):
        """
        Return the Default UoM of the product.
        """
        return self.pool.get('product.product').\
            browse(cr, uid, product_id, context=context).uom_id.id

    def _generate_message(self, msg_list=[], msg_index=False):
        """
        Generation of the message
        """
        res = ''
        if msg_index:
            for m_index in sorted(msg_index):
                if m_index == 0:
                    res += _('Not in file: \n')
                else:
                    res += _('Line %s: \n' % m_index)
                for msg in msg_list[m_index]:
                    res += '    * %s\n' % msg
        else:
            for msg in msg_list:
                res += '%s\n' % msg

        return res

kit_mass_import()
