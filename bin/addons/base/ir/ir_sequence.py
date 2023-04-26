# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.openerp.com>
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

import time
from osv import fields,osv
from tools.translate import _

class ir_sequence_type(osv.osv):
    _name = 'ir.sequence.type'
    _order = 'name'
    _columns = {
        'name': fields.char('Name',size=64, required=True),
        'code': fields.char('Code',size=32, required=True, select=1),
    }
ir_sequence_type()

class ir_sequence(osv.osv):
    _name = 'ir.sequence'
    _order = 'name'

    def _get_number_next_all(self, cr, uid, ids, field, arg, context=None):
        ret = {}
        if not ids:
            return ret
        for seq in self.read(cr, uid, ids, ['number_next', 'implementation']):
            if seq['implementation'] == 'no_gap':
                ret[seq['id']] = seq['number_next']
            else:
                # currval can't be used as it returns the value
                # most recently obtained by nextval for this sequence in the current session
                if not cr.table_exists('pg_sequences'):
                    cr.execute("select last_value, is_called, increment_by from ir_sequence_%03d" % seq['id'])  # not_a_user_entry
                    data = cr.fetchone()
                    ret[seq['id']] = data[0]
                    if data[1]:
                        ret[seq['id']] += data[2]
                else:
                    cr.execute("select last_value, is_called from ir_sequence_%03d" % seq['id'])  # not_a_user_entry
                    data = cr.fetchone()
                    ret[seq['id']] = data[0]
                    if data[1]:
                        cr.execute("select increment_by from pg_sequences where sequencename=%s", ("ir_sequence_%03d" % seq['id'],))
                        d2 = cr.fetchone()
                        ret[seq['id']] += d2[0]


        return ret

    def _check_sequence_type_existence(self, cr, uid, ids, context=None):
        """
        Check that same code exists for a sequence type.
        """
        if context is None:
            context = {}
        for sequence in self.read(cr, uid, ids, ['code']):
            cr.execute('SELECT id FROM ir_sequence_type WHERE code = %s LIMIT 1', (sequence.get('code', ''),))
            tmp_res = cr.fetchall()
            if not tmp_res:
                return False
        return True

    _constraints = [
        (_check_sequence_type_existence, "Sequence type code doesn't exist.", ['code']),
    ]

    _columns = {
        'name': fields.char('Name',size=64, required=True),
        'code': fields.char('Code',size=64, required=True, select=1),
        'active': fields.boolean('Active'),
        'prefix': fields.char('Prefix',size=64, help="Prefix value of the record for the sequence"),
        'suffix': fields.char('Suffix',size=64, help="Suffix value of the record for the sequence"),
        'number_next': fields.integer('Next Number', required=True, help="Next number of this sequence", readonly=1),
        'number_next_all': fields.function(_get_number_next_all, method=1, type='integer', string="Next number"),
        'number_increment': fields.integer('Increment Number', required=True, help="The next number of the sequence will be incremented by this number"),
        'padding' : fields.integer('Number padding', required=True, help="OpenERP will automatically adds some '0' on the left of the 'Next Number' to get the required padding size."),
        'company_id': fields.many2one('res.company', 'Company'),
        'implementation': fields.selection([('no_gap', 'OpenERP Standard'), ('psql', 'PostgreSQL sequence')],
                                           'Implementation', required=True, help="Two sequence object implementations are offered: 'PostgreSQL sequence' "
                                           "and 'OpenERP Standard'. The later is slower than the former and locks the row but forbids any"
                                           " gap in the sequence (while they are possible in the former)."
                                           "*do not change this value on a highly loaded server*"),
    }
    _defaults = {
        'active': lambda *a: True,
        'company_id': lambda s,cr,uid,c: s.pool.get('res.company')._company_default_get(cr, uid, 'ir.sequence', context=c),
        'number_increment': lambda *a: 1,
        'number_next': lambda *a: 1,
        'padding' : lambda *a : 0,
        'implementation': lambda *a : 'no_gap',
    }

    def _create_sequence(self, cr, id, number_increment, number_next):
        """ Create a PostreSQL sequence.

        There is no access rights check.
        """
        if number_increment == 0:
            raise osv.except_osv(_('Warning!'),_("Increment number must not be zero."))
        assert isinstance(id, (int, long))
        sql = "CREATE SEQUENCE ir_sequence_%03d INCREMENT BY %%s START WITH %%s" % id  # not_a_user_entry
        cr.execute(sql, (number_increment, number_next))

    def _drop_sequence(self, cr, ids):
        """ Drop the PostreSQL sequence if it exists.

        There is no access rights check.
        """
        ids = ids if isinstance(ids, (list, tuple)) else [ids]
        names = ','.join('ir_sequence_%03d' % i for i in ids)

        # RESTRICT is the default; it prevents dropping the sequence if an
        # object depends on it.
        cr.execute("DROP SEQUENCE IF EXISTS %s RESTRICT " % names)  # not_a_user_entry

    def _alter_sequence(self, cr, id, number_increment):
        """ Alter a PostreSQL sequence.

        There is no access rights check.
        """
        if number_increment == 0:
            raise osv.except_osv(_('Warning!'),_("Increment number must not be zero."))
        assert isinstance(id, (int, long))
        cr.execute("""
            ALTER SEQUENCE ir_sequence_%03d INCREMENT BY %%s
            """ % id, (number_increment,))  # not_a_user_entry

    def create(self, cr, uid, values, context=None):
        values = self._add_missing_default_values(cr, uid, values, context)
        values['id'] = super(ir_sequence, self).create(cr, uid, values, context)
        if values['implementation'] == 'psql':
            self._create_sequence(cr, values['id'], values['number_increment'], values['number_next'])
        return values['id']

    def unlink(self, cr, uid, ids, context=None):
        super(ir_sequence, self).unlink(cr, uid, ids, context)
        self._drop_sequence(cr, ids)
        return True

    def write(self, cr, uid, ids, values, context=None):
        if not ids:
            return True
        if not isinstance(ids, (list, tuple)):
            ids = [ids]
        new_implementation = values.get('implementation')
        rows = self.read(cr, uid, ids, ['implementation', 'number_increment', 'number_next_all'], context)
        super(ir_sequence, self).write(cr, uid, ids, values, context)

        for row in rows:
            # 4 cases: we test the previous impl. against the new one.
            i = values.get('number_increment', row['number_increment'])
            n = values.get('number_next', row['number_next_all'])
            if row['implementation'] == 'psql':
                if new_implementation in ('psql', None):
                    if 'number_increment' in values:
                        self._alter_sequence(cr, row['id'], i)
                else:
                    self._drop_sequence(cr, row['id'])
                    cr.execute('update %s set number_next=%%s where id=%%s ' % (self._table, ), (n, row['id']))  # not_a_user_entry
            else:
                if new_implementation in ('no_gap', None):
                    pass
                else:
                    self._create_sequence(cr, row['id'], i, int(n))

        return True

    def _interpolate(self, s, d):
        if s:
            return s % d
        return  ''

    def _interpolation_dict(self):
        t = time.localtime() # Actually, the server is always in UTC.
        return {
            'year': time.strftime('%Y', t),
            'month': time.strftime('%m', t),
            'day': time.strftime('%d', t),
            'y': time.strftime('%y', t),
            'doy': time.strftime('%j', t),
            'woy': time.strftime('%W', t),
            'weekday': time.strftime('%w', t),
            'h24': time.strftime('%H', t),
            'h12': time.strftime('%I', t),
            'min': time.strftime('%M', t),
            'sec': time.strftime('%S', t),
        }

    def _process(self, cr, uid, s):
        return self._interpolate(s, self._interpolation_dict())

    def _next(self, cr, uid, seq, context=None):
        if not seq:
            return False
        if context is None:
            context = {}
        try:
            interpolated_prefix = self._process(cr, uid, seq['prefix'])
            interpolated_suffix = self._process(cr, uid, seq['suffix'])
        except ValueError:
            raise osv.except_osv(_('Warning'), _('Invalid prefix or suffix for sequence \'%s\'') % (seq.get('name')))
        if seq['implementation'] == 'psql':
            cr.execute("SELECT nextval('ir_sequence_%03d')" % seq['id'])  # not_a_user_entry
            seq['number_next'] = cr.fetchone()
        else:
            cr.execute("SELECT number_next FROM ir_sequence WHERE id=%s FOR UPDATE NOWAIT", (seq['id'],))
            seq['number_next'] = cr.fetchone()
            cr.execute("UPDATE ir_sequence SET number_next=number_next+number_increment WHERE id=%s ", (seq['id'],))
        #d = self._interpolation_dict()
        return interpolated_prefix + '%%0%sd' % seq['padding'] % seq['number_next'] + interpolated_suffix

    def get_id(self, cr, uid, sequence_code_or_id, code_or_id='id', context=None):
        """ Draw an interpolated string using the specified sequence.

        The sequence to use is specified by the ``sequence_code_or_id``
        argument, which can be a code or an id (as controlled by the
        ``code_or_id`` argument. This method is deprecated.
        """
        assert code_or_id in ('code','id')
        company_ids = self.pool.get('res.company').search(cr, uid, [], context=context)
        cr.execute('''SELECT id, implementation, prefix, suffix, padding, number_next, name
            FROM ir_sequence
            WHERE %s=%%s
              AND active=true
              AND (company_id in %%s or company_id is NULL)
            ORDER BY company_id, id''' % code_or_id, (sequence_code_or_id, tuple(company_ids)))  # not_a_user_entry
        res = cr.dictfetchone()
        return self._next(cr, uid, res, context=context)

    def get(self, cr, uid, code):
        return self.get_id(cr, uid, code, code_or_id='code')

ir_sequence()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
