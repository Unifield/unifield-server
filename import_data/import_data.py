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

from osv import osv, fields
from tools.translate import _
import csv
import threading
from tempfile import TemporaryFile
import base64
import pooler
import tools
from mx import DateTime
import re
import logging

class import_data(osv.osv_memory):
    _name = 'import_data'
    _description = 'Import Datas'

    def _set_code_name(self, cr, uid, data, row):
        if not data.get('name'):
            data['name'] = row[0]
        if not data.get('code'):
            data['code'] = row[0]

    def _set_nomen_level(self, cr, uid, data, row):
        if data.get('parent_id'):
            v = self.onChangeParentId(cr, uid, id, data.get('type'), data['parent_id'])
            if v['value']['level']:
                data['level'] = v['value']['level']

    def _set_full_path_nomen(self, cr, uid, headers, row, col):
        if not col:
            self._cache = {}
            # modify headers if needed
            for n,h in enumerate(headers):
                m = re.match("^nomen_manda_([0123]).name$", h)
                if m:
                    col[int(m.group(1))] = n
                    headers[n] = "nomen_manda_%s.complete_name"%(m.group(1), )

        if row:
            for manda in sorted(col.keys()):
                if manda != 0:
                    row[col[manda]] = ' / '.join([row[col[manda-1]], row[col[manda]]])
        return col

    def _del_product_cache(self, cr, uid):
        self._cache = {}

    post_hook = {
        'account.budget.post': _set_code_name,
        'product.nomenclature': _set_nomen_level,
    }

    pre_hook = {
        'product.product': _set_full_path_nomen, 
    }

    post_load_hook = {
        'product.product': _del_product_cache,
    }

    def _get_image(self, cr, uid, context=None):
        return self.pool.get('ir.wizard.screen')._get_image(cr, uid)

    _columns = {
        'ignore': fields.integer('Number of headers to ignore', required=True),
        'file': fields.binary('File', required=True),
        'debug': fields.boolean('Debug to server log'),
        'object': fields.selection([
            ('product.nomenclature','Product Nomenclature'),
            ('product.category','Product Category'), 
            ('product.product', 'Product'),
            ('res.partner.category','Partner Category'),
            ('res.partner','Partner'),
            ('stock.location','Location'),
            ('stock.warehouse','Warehouse'),
            ('account.analytic.account','Analytic Account'),
            ('crossovered.budget','Budget'),
            ('account.budget.post','Budget Line'),
            ('product.supplierinfo', 'Supplier Info'),
            ], 'Object' ,required=True),
        'config_logo': fields.binary('Image', readonly='1'),
    }

    _defaults = {
        'ignore': lambda *a : 1,
        'config_logo': _get_image,
        'debug': False,
    }

    def _import(self, dbname, uid, ids, context=None):
        cr = pooler.get_db(dbname).cursor()

        obj = self.read(cr, uid, ids[0])
        
        objname = ""
        for sel in self._columns['object'].selection:
            if sel[0] == obj['object']:
                objname = sel[1]
                break
        
        fileobj = TemporaryFile('w+')
        fileobj.write(base64.decodestring(obj['file']))
        fileobj.seek(0)
        impobj = self.pool.get(obj['object'])
        reader = csv.reader(fileobj, quotechar='"', delimiter=';')

        errorfile = TemporaryFile('w+')
        writer = csv.writer(errorfile, quotechar='"', delimiter=';')

        fields_def = impobj.fields_get(cr, uid, context=context)
        i = 0
        while reader and obj['ignore'] > i:
            i += 1
            r = reader.next()
            if r and r[0].split('.')[0] in fields_def:
                headers = r[:]

        def _get_obj(header, value, fields_def):
            list_obj = header.split('.')
            relation = fields_def[list_obj[0]]['relation']
            new_obj = self.pool.get(relation)
            newids = new_obj.search(cr, uid, [(list_obj[1], '=', value)], limit=1)
            if not newids:
                # TODO: no obj
                raise osv.except_osv(_('Warning !'), '%s does not exist'%(value,))
            return newids[0]

        def process_data(field, value, fields_def):
            if not value:
                return 
            if '.' not in field:
                # type datetime, date, bool, int, float
                if value and fields_def[field]['type'] == 'boolean':
                    value = value.lower() not in ('0', 'false', 'off','-', 'no', 'n')
                elif value and fields_def[field]['type'] == 'selection':
                    for key, val in fields_def[field]['selection']:
                        if value.lower() in [tools.ustr(key).lower(), tools.ustr(val).lower()]:
                            value = key
                            break
                elif value and fields_def[field]['type'] == 'date':
                    dt = DateTime.strptime(value,"%d/%m/%Y")
                    value = dt.strftime("%Y-%m-%d") 
                elif value and fields_def[field]['type'] == 'float':
                    # remove space and unbreakable space
                    value = re.sub('[  ]+', '', value)
                    value = float(value.replace(',', '.'))
                return value

            else:
                if fields_def[field.split('.')[0]]['type'] in 'many2one':
                    return _get_obj(field, value, fields_def)
            
            raise osv.except_osv(_('Warning !'), '%s does not exist'%(value,))
        
        i = 1
        nb_error = 0
        nb_succes = 0
        col_datas = {}
        if self.pre_hook.get(impobj._name):
            # for headers mod.
            col_datas = self.pre_hook[impobj._name](impobj, cr, uid, headers, {}, col_datas)
        writer.writerow(headers)

        for row in reader:
            newo2m = False
            delimiter = False
            o2mdatas = {}
            i += 1
            if i%101 == 0 and obj['debug']:
                logging.getLogger('import data').info('Object: %s, Item: %s'%(obj['object'],i))

            if not row:
                continue
            empty = True
            for r in row:
                if r:
                    empty = False
                    break
            if empty:
                continue
            data = {}
            try:
                n = 0
                if self.pre_hook.get(impobj._name):
                    self.pre_hook[impobj._name](impobj, cr, uid, headers, row, col_datas)

                for n,h in enumerate(headers):
                    row[n] = row[n].rstrip()
                    if newo2m and ('.' not in h or h.split('.')[0] != newo2m or h.split('.')[1] == delimiter):
                        data.setdefault(newo2m, []).append((0, 0, o2mdatas.copy()))
                        o2mdatas = {}
                        delimiter = False
                        newo2m = False
                    if '.' not in h:
                        # type datetime, date, bool, int, float
                        value = process_data(h, row[n], fields_def)
                        if value is not None:
                            data[h] = value
                    else:
                        points = h.split('.')
                        if row[n] and fields_def[points[0]]['type'] == 'one2many':
                            newo2m = points[0]
                            delimiter = points[1]
                            new_fields_def = self.pool.get(fields_def[newo2m]['relation']).fields_get(cr, uid, context=context)
                            o2mdatas[points[1]] = process_data('.'.join(points[1:]), row[n], new_fields_def)
                        elif row[n] and fields_def[points[0]]['type'] in 'many2one':
                            data[points[0]] = _get_obj(h, row[n], fields_def) or False
                        elif fields_def[points[0]]['type'] in 'many2many' and row[n]:
                            data.setdefault(points[0], []).append((4, _get_obj(h, row[n], fields_def)))
                if newo2m and o2mdatas:
                    data.setdefault(newo2m, []).append((0, 0, o2mdatas.copy()))
                
                if self.post_hook.get(impobj._name):
                    self.post_hook[impobj._name](impobj, cr, uid, data, row)
               
                impobj.create(cr, uid, data)
                nb_succes += 1
            except osv.except_osv, e:
                logging.getLogger('import data').info('Error %s'%e.value)
                cr.commit()
                row.append("Line %s, row: %s, %s"%(i, n, e.value))
                writer.writerow(row)
                nb_error += 1
            except Exception, e:
                cr.commit()
                logging.getLogger('import data').info('Error %s'%e)
                row.append("Line %s, row: %s, %s"%(i, n, e))
                writer.writerow(row)
                nb_error += 1

        if self.post_load_hook.get(impobj._name):
            self.post_load_hook[impobj._name](impobj, cr, uid)
        fileobj.close()
        summary = '''Datas Import Summary: 
Object: %s
Records created: %s
'''%(objname, nb_succes)

        if nb_error:
            summary += '''Records rejected: %s

Find in attachment the rejected lines'''%(nb_error)

        request_obj = self.pool.get('res.request')
        req_id = request_obj.create(cr, uid,
            {'name': "Import %s"%(objname,),
            'act_from': uid,
            'act_to': uid,
            'body': summary,
            })
        if req_id:
            request_obj.request_send(cr, uid, [req_id])

        if nb_error:
            errorfile.seek(0)
            attachment = self.pool.get('ir.attachment')
            attachment.create(cr, uid, {
                'name': 'rejected-lines.csv',
                'datas_fname': 'rejected-lines.csv',
                'description': 'Rejected Lines',
                'res_model': 'res.request',
                'res_id': req_id,
                'datas': base64.encodestring(errorfile.read()), 
            })

        errorfile.close()
        cr.commit()
        cr.close()

    def import_csv(self, cr, uid, ids, context={}):
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        return {'type': 'ir.actions.act_window_close'}

import_data()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
