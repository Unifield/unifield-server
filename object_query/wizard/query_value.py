# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
from tools.translate import _
from tools.safe_eval import safe_eval

class search_values(osv.osv_memory):
    _name ="object.query.wizard.values"
    _columns = {
        'query_id': fields.many2one('object.query', 'Query'),
        'b_data': fields.binary('Datas'),
    }

    def compute(self, cr, uid, ids, context):
        line_obj = self.pool.get('object.query.selection_data')
        datas = self.read(cr, uid, ids[0])
        data = datas['b_data']
        old_lines = line_obj.search(cr, uid, [('query_id', '=', datas['query_id'])])
        if old_lines:
            line_obj.unlink(cr, uid, old_lines)
        for v in data:
            if '_' in v:
                field_info, limit = v.split('_')
                if limit == 'to':
                    continue
                value = data[v]
                value2 = data["%s_to"%(field_info, )]
            else:
                field_info = v
                value = data[v]
                value2 = False
            if value or value2:
                line_obj.create(cr, uid, {'query_id': datas['query_id'], 'field_id': field_info, 'value1': value, 'value2': value2})
        return { 'type': 'ir.actions.act_window_close'}

    def create(self, cr, uid, vals, context={}):
        return super(search_values, self).create(cr, uid, {'b_data': vals, 'query_id': context.get('query_id')}, {'no_missing': True})

    def default_get(self, cr, uid, fields_list, context=None):
        if context is None:
            context = {}
        if context.get('no_missing'):
            return {}

        if not context.get('query_id'):
            raise osv.except_osv(_('Error'), _('Error in context'))

        obj_q = self.pool.get('object.query').browse(cr, uid, context['query_id'])
        values = {}
        for v  in obj_q.selection_data:
            if v.field_id.ttype in ('date', 'datetime', 'int', 'float'):
                values['%s_from'%(v.field_id.id, )] = v.value1
                values['%s_to'%(v.field_id.id, )] = v.value2
            else:
                if v.field_id.ttype == 'many2one':
                    values['%s'%v.field_id.id] = v.value1 and int(v.value1)
                else:
                    values['%s'%v.field_id.id] = v.value1
        return values

    def fields_get(self, cr, uid, fields=None, context={}):
        if context is None:
            context = {}
        if not context.get('query_id'):
            raise osv.except_osv(_('Error'), _('Error in context'))

        obj_q = self.pool.get('object.query').browse(cr, uid, context['query_id'])
        quest_fields = super(search_values, self).fields_get(cr, uid, fields, context)

        values = {}
        for v  in obj_q.selection_data:
            if v.field_id.ttype in ('date', 'datetime', 'int', 'float'):
                values['%s_from'%(v.field_id.id, )] = v.value1
                values['%s_to'%(v.field_id.id, )] = v.value2
            else:
                values[v.field_id.id] = v.value1
        
        for sel in obj_q.selection_ids:
            field_name = '%s'%(sel.id)
            if sel.ttype in ('date', 'datetime', 'int', 'float'):
                quest_fields[field_name+'_from'] = {'type': sel.ttype, 'string': sel.field_description, 'default':values.get(field_name+'_from', False)}
                quest_fields[field_name+'_to'] = {'type': sel.ttype, 'string': sel.field_description, 'default':values.get(field_name+'_to', False)}

            else:
                quest_fields[field_name] = {'string': sel.field_description, 'default':values.get(sel.id, False)}
                if sel.ttype == 'selection':
                    selection = list(self.pool.get(sel.model)._columns[sel.name].selection)
                    selection.insert(0, ('',''))
                    quest_fields[field_name].update({'type': 'selection', 'selection': selection})
                elif sel.ttype == 'many2one':
                    quest_fields[field_name].update({'type': sel.ttype, 'relation': sel.relation, 'default':int(values.get(sel.id, 0))})
                elif sel.ttype == 'boolean':
                    quest_fields[field_name].update({'type': 'selection', 'selection': [('t','Yes'), ('f', 'No')]})
                else:
                    quest_fields[field_name].update({'type': 'char', 'size':1024})
        return quest_fields

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context={}, toolbar=False, submenu=False):
        if context is None:
            context = {}
        ret = {}
        if not context.get('query_id'):
            raise osv.except_osv(_('Error'), _('Error in context'))

        obj_q = self.pool.get('object.query').browse(cr, uid, context['query_id'])
        quest_form = '<form string="Values">'
        for sel in obj_q.selection_ids:
            field_name = '%s'%(sel.id)
            if sel.ttype in ('date', 'datetime', 'int', 'float'):
                quest_form += '<group colspan="4" col="5"><field name="%s_from" /> <label string="-"/><field name="%s_to" nolabel="1" colspan="2"/></group>'%(field_name, field_name)
            else:
                quest_form += '<field name="%s" /> <newline/>'%(field_name,)
        quest_form += ''''<group colspan="4">
            <button special="cancel" string="Cancel" icon="gtk-cancel" type="object" colspan="2"/>
            <button string="Save" icon="gtk-execute" name="compute" type="object" colspan="2"/>
        </group>
        </form>'''
        ret['arch'] = quest_form
        ret['fields'] = self.fields_get(cr, uid, None, context)
        return ret

search_values()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

