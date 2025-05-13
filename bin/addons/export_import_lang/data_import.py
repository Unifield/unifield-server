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

import tools
from osv import osv, fields
import csv
from tools.translate import _
import threading
import pooler
from . import lang_tools

class msf_language_import(osv.osv_memory):
    """ Language Import """

    _name = "msf.language.import"
    _description = "Language Import"
    _inherit = "ir.wizard.screen"

    def open_requests(self, cr, uid, ids, context=None):
        return lang_tools.open_requests(self, cr, uid, ids, 'import', context)

    def _get_languages(self, cr, uid, context=None):
        return self.pool.get('base.language.export')._get_languages(cr, uid, context)

    _columns = {
        'name': fields.selection(_get_languages, 'Language', required=1),
        'data': fields.binary('File', required=True),
    }

    _defaults = {
        'name': lambda *a: 'fr_MF',
    }

    def import_data_lang(self, cr, uid, ids, context):
        """
        This method is for importing the data translation in MSF
        """
        thread = threading.Thread(target=self._import_data_bg, args=(cr.dbname, uid, ids, context))
        thread.start()
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'export_import_lang', 'view_msf_import_language_2')[1]
        return {
            'view_mode': 'form',
            'view_id': [view_id],
            'view_type': 'form',
            'res_model': 'msf.language.import',
            'res_id': ids[0],
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'new'
        }

    def _import_data_bg(self, dbname, uid, ids, context):

        try:
            cr = pooler.get_db(dbname).cursor()
            import_data = self.browse(cr, uid, ids)[0]
            fileobj, fileformat = lang_tools.get_data_file(cr, uid, import_data.data)

            reader = csv.DictReader(fileobj, delimiter=",",quotechar='"')
            rejected = []
            trans_obj = self.pool.get('ir.translation')
            line = 0
            for row in reader:
                line += 1
                try:
                    if not row.get('value') or not row.get('name'):
                        rejected.append(_('Line %s, incorrect column number value and name should not be empty.') % (line+1, ))
                        continue
                    if ',' not in row['name']:
                        rejected.append(_('Line %s, Column B: Incorrect format') % (line+1, ))
                        continue

                    # US-145: regular import or specific product description ?
                    is_product_name_import = True if row['name'] == 'product.product,name' else False
                    if not is_product_name_import:
                        # regular import
                        if not row.get('src'):
                            rejected.append(_('Line %s, incorrect column number src should not be empty.') % (line+1, ))
                            continue
                    else:
                        # specific product description (default_code as key)
                        # src not mandatory for a product description translation (only a referential)...
                        # http://jira.unifield.org/browse/US-145?focusedCommentId=39852&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-39852
                        # ...BUT 'Notes' mandatory: the product code
                        if not row.get('Notes'):
                            rejected.append(_('Line %s, incorrect column number Notes should not be empty for a product description translation: contains the product code.') % (line+1, ))
                            continue

                    obj, field = row['name'].split(',', 1)
                    obj = obj.strip()
                    search_obj = obj
                    field = field.strip()
                    search_field = field
                    src = row['src']
                    search_src = src
                    if obj == 'product.product' and field == 'name':
                        # search for product code in product.product but work
                        # with translated field name in product.template
                        obj = 'product.template'
                        search_field = 'default_code'
                        search_src = row.get('Notes')

                    obj_ids = self.pool.get(search_obj).search(cr, uid, [(search_field, '=', search_src)], context={'lang': 'en_US', 'active_test': False})
                    if not obj_ids:
                        rejected.append(_('Line %s Record %s not found') % (line+1, search_src.decode('utf-8')))
                        continue
                    # BKLG-52: If the translation for a data entry exists already in ir.translation, then just update the new translation, no need to delete-recreate!
                    # This is then avoid having the delete sync to send to other instances
                    for trans_id in obj_ids:
                        name = '%s,%s' % (obj, field)
                        args = [('lang', '=', import_data.name), ('type', '=', 'model'),
                                ('name', '=', name), ('res_id', '=', trans_id)]
                        translation_ids = trans_obj.search(cr, uid, args, offset=0, limit=None, order=None, context=context, count=False)
                        # if the translation existed for this record, then just update it, otherwise create a new one
                        if translation_ids:
                            values = {'value': row['value']}
                            trans_obj.write(cr, uid, translation_ids[0], values, context=context)
                        else:
                            if is_product_name_import:
                                # ALWAYS get english original src name ('en_US' in context)
                                # as now default_code is the key in csv file
                                src = self.pool.get(obj).read(cr, uid,
                                                              [trans_id], ['name'],
                                                              context={'lang': 'en_US', })[0]['name']
                            trans_obj.create(cr, uid, {
                                'lang': import_data.name,
                                'type': 'model',
                                'name': name,
                                'res_id': trans_id,
                                'value': row['value'],
                                'src': src,
                            })
                    cr.commit()
                except Exception as e:
                    cr.rollback()
                    rejected.append(_('Line %s, system error: %s') % (line+1, e))

            tools.cache.clean_caches_for_db(cr.dbname)
            fileobj.close()
            req_obj = self.pool.get('res.request')

            req_val = {
                'name': _('Import Translation Data: %s/%s') % (line-len(rejected), line),
                'act_from': uid,
                'act_to': uid,
                'import_trans': True,
            }
            if rejected:
                req_val['body'] =  _("The following lines couldn't be imported:\n%s") % ("\n".join(rejected), )
            else:
                req_val['body'] = _("Your translation file has been successfully imported.")

            req_id = req_obj.create(cr, uid, req_val)
            req_obj.request_send(cr, uid, [req_id])

            self.write(cr, uid, [ids[0]], {'data': ''})
            cr.commit()
            cr.close(True)

        except Exception as e:
            cr.rollback()
            self.write(cr, uid, [ids[0]], {'data': ''})
            req_id = self.pool.get('res.request').create(cr, uid, {
                'name': _('Import translation failed'),
                'act_from': uid,
                'act_to': uid,
                'import_trans': True,
                'body': _('''The process to import the translation file failed !
                %s
                ''') % (e,)
            })
            cr.commit()
            cr.close(True)
            raise

        return {}

msf_language_import()
