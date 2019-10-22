# -*- coding: utf-8 -*-

from osv import osv, fields
from tools.translate import _
import time

class replenishment_location_config(osv.osv):
    _name = 'replenishment.location.config'
    _description = 'Location Configuration'
    _order = 'id desc'


    def _get_frequence_name(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the name_get value of the frequence
        '''
        res = {}
        for proc in self.browse(cr, uid, ids):
            if proc.frequence_id:
                res[proc.id] = self.pool.get('stock.frequence').name_get(cr, uid, [proc.frequence_id.id], context=context)[0][1]
        return res


    _columns = {
        'name': fields.char('Reference', size=64, readonly=1, select=1),
        'description': fields.char('Desription', required=1, size=28, select=1),
        'synched': fields.boolean('Synched Locations'),
        'main_instance': fields.many2one('msf.instance', readonly=1, string="Main Instance"),
        'active': fields.boolean('Active'),
        'local_location_ids': fields.many2many('stock.location', 'local_location_configuration_rel', 'config_id', 'location_id', 'Local Locations', domain="[('usage', '=', 'internal'), ('location_category', 'in', ['stock', 'consumption_unit', 'eprep']), ('used_in_config', '=', False)]"),
        'remote_location_ids': fields.many2many('stock.location.instance', 'remote_location_configuration_rel', 'config_id', 'location_id', 'Project Locations', domain="[('usage', '!=', 'view'), ('used_in_config', '=', False)]"),

        # iventory review
        'review_active': fields.boolean('Review Active'),
        'projected_view': fields.integer('Standard Projected view (months)'),
        'rr_amc': fields.integer('RR-AMC period (months)'),
        'sleeping': fields.integer('Sleeping stock periodicity (months)'),
        'time_unit': fields.selection([('d', 'days'), ('w', 'weeks'), ('m', 'months')], string='Time units displayed (Inventory Review)'),
        'frequence_name': fields.function(_get_frequence_name, method=True, string='Frequency', type='char'),
        'frequence_id': fields.many2one('stock.frequence', string='Frequency'),
    }

    _defaults = {
        'active': True,
        'synched': True,
        'main_instance': lambda s, cr, uid, c: s.pool.get('res.company')._get_instance_id(cr, uid),
        'projected_view': 8,
        'sleeping': 12,
    }

    def write(self, cr, uid, ids, vals, context=None):
        if 'synched' in vals and not vals['synched']:
            vals['remote_location_ids'] = [(6, 0, [])]

        return super(replenishment_location_config, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        if 'name' not in vals:
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'replenishment.location.config')

        if 'synched' in vals and not vals['synched']:
            vals['remote_location_ids'] = [(6, 0, [])]

        return super(replenishment_location_config, self).create(cr, uid, vals, context)

    def check_no_duplicates(self, cr, uid, ids, context=None):
        instance_id = self.pool.get('res.company')._get_instance_id(cr, uid)
        error = []

        for location_table, location_name, rel_table in [('stock_location', 'name', 'local_location_configuration_rel'), ('stock_location_instance', 'full_name', 'remote_location_configuration_rel')]:
            cr.execute('''
                select config.description, config2.name, loc.''' + location_name + ''' from
                    replenishment_location_config config, ''' + rel_table + ''' rel, replenishment_location_config config2, ''' + rel_table + ''' rel2, ''' + location_table + ''' loc
                where
                    rel.config_id = config.id and
                    config.main_instance = %(instance)s and
                    config.id in %(ids)s and
                    rel2.config_id = config2.id and
                    config2.main_instance = %(instance)s and
                    config2.id != config.id and
                    rel.location_id = rel2.location_id and
                    config.active and
                    config2.active and
                    loc.id = rel.location_id
                group by config.description, config2.name, loc.id, loc.name
            ''', {'instance': instance_id, 'ids': tuple(ids)})   # not_a_user_entry
            nb_error = 0
            for x in cr.fetchall():
                if nb_error > 5:
                    error.append('...')
                    break
                error.append(_('%s : location %s already used in %s') % (x[0], x[2], x[1]))
                nb_error += 1
        if error:
            raise osv.except_osv(_('Warning'), "\n".join(error))
        return True

    _constraints = [(check_no_duplicates, 'Location already used on an active Configuration', [])]
    _sql_constraints = [
        ('unique_description_instance', 'unique(description, main_instance)', 'Desription must be unique'),
        ('review_active_with_freq', 'CHECK(review_active or frequence_id is not null)', "You can't activate a review w/o any frequency"),
    ]


    def choose_change_frequence(self, cr, uid, ids, context=None):
        '''
        Open a wizard to define a frequency for the automatic supply
        or open a wizard to modify the frequency if frequency already exists
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        proc = self.browse(cr, uid, ids[0], fields_to_fetch=['frequence_id'], context=context)
        if proc.frequence_id and proc.frequence_id.id:
            frequence_id = proc.frequence_id.id
        else:
            frequence_data = {
                'name': 'monthly',
                'monthly_choose_freq': 1,
                'monthly_choose_day': 'monday',
                'monthly_frequency': 1,
                'monthly_one_day': True,
                'no_end_date': True,
                'start_date': time.strftime('%Y-%m-%d'),
            }
            frequence_id = self.pool.get('stock.frequence').create(cr, uid, frequence_data, context=context)
            self.write(cr, uid, proc.id, {'frequence_id': frequence_id}, context=context)

        context.update({
            'active_id': proc.id,
            'active_model': 'replenishment.location.config',
            'res_ok': True,
        })

        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'stock.frequence',
            'view_type': 'form',
            'view_model': 'form',
            'context': context,
            'res_id': frequence_id
        }

replenishment_location_config()


