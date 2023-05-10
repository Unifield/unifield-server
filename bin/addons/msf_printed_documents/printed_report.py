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
from tools.safe_eval import safe_eval
import re

HELP_TARGET = '''
          This field will be parsed by the system to compute the good filename.

          Possible elements:

          ${field_name}     => Get the value of the field 'field_name' of the document.
                               You can use a dot field_name (e.g. : partner_id.name) to
                               get the value of the field of a many2one
          ${eval(function)} => Return the value of the function. The function is a 
                               method of the object like function(self, cr, uid, ids)

          ${_('String')}    => translate String
          %(year)s          => Current year (e.g: 2013, 2014, ...)
          %(month)s         => Current month number (e.g: 01, 02, ..., 12)
          %(day)s           => Current day of month number (e.g: 25)
          %(y)s             => Current year without century (e.g: 02,03, ...,99)
          %(doy)s           => Current day of the year (e.g: 001, 002, ..., 366)
          %(woy)s           => Current week number of the year
          %(weekday)s       => Current weekday as decimal number where 0 is Sunday
          %(h24)s           => Current hour (24-hour clock)
          %(h12)s           => Current hour (12-hour clock)
          %(min)s           => Current minute
          %(sec)s           => Current second
          %(instance)s      => Instance code
          %(hqcode)s        => HQ instance code'''

class ir_actions_report_xml(osv.osv):
    _inherit = 'ir.actions.report.xml'

    def parse_filename(self, cr, uid, report, active_model, active_id, context=None):
        '''
        Parse the filename to get the good filename.

        - If no target filename defined on the report, try to set the name as :
          XXX_doc_name where XXX is the first letter of each word of report name
          and doc_name is the value of the field 'name' of the document.

        - If a target filename is set on the report, parse the target filename to
          compute the good name.

          Available templates:
          ####################

          ${field_name}     => Get the value of the field 'field_name' of the document.
                               You can use a dot field_name (e.g. : partner_id.name) to
                               get the value of the field of a many2one
          ${eval(function)} => Return the value of the function. The function is a 
                               method of the object like function(self, cr, uid, ids)

          %(year)s          => Current year (e.g: 2013, 2014, ...)
          %(month)s         => Current month number (e.g: 01, 02, ..., 12)
          %(day)s           => Current day of month number (e.g: 25)
          %(y)s             => Current year without century (e.g: 02,03, ...,99)
          %(doy)s           => Current day of the year (e.g: 001, 002, ..., 366)
          %(woy)s           => Current week number of the year
          %(weekday)s       => Current weekday as decimal number where 0 is Sunday
          %(h24)s           => Current hour (24-hour clock)
          %(h12)s           => Current hour (12-hour clock)
          %(min)s           => Current minute
          %(sec)s           => Current second
          %(instance)s      => Instance code
          %(hqcode)s        => HQ instance code
        '''
        context = context or {}

        if not report.target_filename:
            if active_model and active_id:
                report_letters = ''.join(item[0].upper() for item in re.findall("\w+", report.name))
                try:
                    return '%s_%s' % (report_letters, self.pool.get(active_model).read(cr, uid, active_id, ['name'])['name'])
                except KeyError:
                    return False
            else:
                return False

        error = ''
        if report.target_filename:
            report_name = self.pool.get('ir.sequence')._process(cr, uid, report.target_filename)
            values_to_compute = re.findall('\${((?:[\'"\w]+.?)*)}', report_name)
            vals_dict = {}
            # No possibility to compute the file name
            if values_to_compute and not active_model or not active_id:
                return False

            parse_string = report_name.replace('${', '%(').replace('}', ')s')
            model_obj = self.pool.get(active_model)

            for field_name in values_to_compute:
                vals_dict[field_name] = ''
                model_doc = model_obj.browse(cr, uid, active_id, context=context)
                # Use a function to compute the name
                if field_name.startswith('_'+'('): # '_' + '(' : to disable export of translations
                    to_trans = field_name[3:-2]
                    vals_dict[field_name] = _(to_trans)
                    continue
                if field_name.startswith('eval'):
                    func_name = field_name[5:-1]
                    try:
                        vals_dict.update({field_name: getattr(model_doc, func_name)(context=context)})
                        continue
                    except AttributeError:
                        error += _('%s : The function \'%s\' is not a valid function for the \'%s\' model.\n') % (field_name, func_name, report.model._name)
                        break

                or_field = field_name.split(' or ')
                for orf in or_field:
                    split_field = orf.split('.')
                    split_len = len(split_field)
                    field = split_field[-1]
                    i = 0
                    while i < split_len-1:
                        model_doc = model_doc[split_field[i]]
                        i += 1

                    if model_doc[field]:
                        res = model_doc[field]
                        # If the field is a selection, get the real name of the selection
                        # If the field is a many2one without any other field, get the name of the many2one
                        if isinstance(model_doc._columns[field], fields.selection):
                            res = self.pool.get('ir.model.fields').get_browse_selection(cr, uid, model_doc, field, context)
                        elif isinstance(model_doc._columns[field], fields.many2one):
                            res = model_doc[field]['name']

                        vals_dict.update({field_name: res})
                        break

        return parse_string % vals_dict

    def _get_filename(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the name of the file that will be generated
        '''
        context = context or {}

        res = {}

        active_model = context.get('model')
        active_id = context.get('id')
        d_context = context.get('context', {})

        for report in self.browse(cr, uid, ids, context=context):
            parsed_name = self.parse_filename(cr, uid, report, active_model, active_id, context=d_context)
            if parsed_name:
                res[report.id] = parsed_name.replace(',', '-')
            else:
                res[report.id] = report.name

        return res


    _columns = {
        'target_filename': fields.char(size=128, string='Target filename', help=HELP_TARGET),
        'filename': fields.function(_get_filename, method=True, string='Filename', type='char'),
    }

    def _check_target_validity(self, cr, uid, ids, context=None):
        '''
        Check the validity of the target filename of the report
        '''
        valid_fields_type = (
            fields.many2one,
            fields.selection,
            fields.char,
            fields.float,
            fields.integer,
            fields.date,
            fields.datetime,
            fields.time,
        )
        bad_type = False

        for report in self.browse(cr, uid, ids, context=context):
            if not report.target_filename:
                continue

            error = ''
            try:
                if self.pool.get('res.company')._get_instance_record(cr, uid):
                    report_name = self.pool.get('ir.sequence')._process(cr, uid, report.target_filename)
                else:
                    report_name = report.target_filename
            except KeyError as e:
                # Some %(blabla)s remain, cannot parse them
                error += _('\'%%(%s)s\' cannot be parsed \n') % e
                raise osv.except_osv(_('Error'), error)
                break

            # Check if the fields in ${} are valid
            fields_name = re.findall('\${((?:[\'"\w+].?)*)}', report_name)
            for field_name in fields_name:
                # Use a function to compute the name
                if field_name.startswith('_'+'('): # disable translation export
                    try:
                        safe_eval(field_name, locals_dict={'_': lambda *x: x})
                    except:
                        error += _('%s : invalid syntax') % field_name
                        break
                    continue
                if field_name.startswith('eval'):
                    func_name = field_name[5:-1]
                    model_doc = self.pool.get(report.model)
                    try:
                        getattr(model_doc, func_name)
                        continue
                    except AttributeError:
                        error += _('%s : The function \'%s\' is not a valid function for the \'%s\' model.\n') % (field_name, func_name, model_doc._name)
                        break

                model_doc = self.pool.get(report.model)

                or_field = field_name.split(' or ')
                for orf in or_field:
                    split_field = orf.split('.')
                    split_len = len(split_field)
                    field = split_field[-1]
                    i = 0
                    while i < split_len-1:
                        if split_field[i] not in model_doc._columns:
                            error += _('%s : The field \'%s\' is not in \'%s\' model.\n') % (field_name, split_field[i], model_doc._name)
                            break
                        if isinstance(model_doc._columns[split_field[i]], fields.many2one):
                            model_doc = self.pool.get(model_doc._columns[split_field[i]]._obj)
                        else:
                            error += _('%s : The field \'%s\' is not a many2one field. Cannot parse this expression.\n') % (field_name, split_field[i])
                            break
                        i += 1

                    if field not in model_doc._columns:
                        error += _('%s : The field \'%s\' is not in \'%s\' model.\n') % (field_name, split_field[i], model_doc._name)
                        break
                        if not isinstance(model_doc._columns[field], valid_fields_type):
                            bad_type = True
                            error += _('%s : The field \'%s\' is not a valid field type for report name.\n') % (field_name, field)

            if bad_type:
                error += _('''Valid field types : 
                    - many2one (with a field of the relation (e.g: partner_id.name)
                    - selection
                    - char
                    - float
                    - integer
                    - date
                    - datetime
                    - time''')

            if error:
                raise osv.except_osv(_('Error'), error)

        return True

    _constraints = [
        (_check_target_validity, 'The target filename given is not valid', ['target_filename']),
    ]

ir_actions_report_xml()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
