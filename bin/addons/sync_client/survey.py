# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
import tools
import time


class survey_common(osv.osv):
    _name = 'survey.common'
    _description = 'Survey common class client / server'
    _auto = False

    def _search_date_filter(self, cr, uid, obj, name, args, context=None):
        dom = []
        for arg in args:
            curr_date = time.strftime('%Y-%m-%d %H:%M:%S')
            if arg[2] == 'current':
                dom = ['&', ('start_date','<=', curr_date), ('end_date', '>=', curr_date)]
            elif arg[2] == 'future':
                dom = [('start_date', '>=', curr_date)]
        return dom

    _columns = {
        'name': fields.char('Name (EN)', size=1024, required=1),
        'name_fr': fields.char('Name (FR)', size=1024, required=1),
        'profile': fields.char('Profile Name', size=1024, required=1),
        'start_date': fields.datetime('Date Start', required=1),
        'end_date': fields.datetime('Date End', required=1),
        'url_en': fields.char('English URL', size=1024, required=1),
        'url_fr': fields.char('French URL', size=1024, required=1),
        'date_filter': fields.function(tools.misc.get_fake, type='char', string='Filter on dates', method=True, fnct_search=_search_date_filter),
        'active': fields.boolean('Active'),
        'server_write_date': fields.datetime('Sync server last mod', select=1),
        'include_condition': fields.selection([('and', 'AND'), ('or', 'OR')], 'Included groups condition', required=1),
    }

    _defaults = {
        'include_condition': 'or',
        'active': True,
    }

    def get_last_write(self, cr, uid):
        cr.execute('select max(server_write_date) from %s' % (self._table, )) # not_a_user_entry
        r = cr.fetchone()
        return r and r[0] or False

survey_common()

class sync_client_survey(osv.osv):
    _inherit = 'survey.common'
    _name = 'sync_client.survey'
    _descrpition = 'Survey'
    _order = 'start_date desc'
    _auto = True

    def _get_users(self, cr, uid, ids, fields, args, context=None):
        res = {}
        for _id in ids:
            res[_id] = []

        cr.execute('''
            select
                survey.id, u.id
            from
                res_users u
                inner join res_groups_users_rel rel on rel.uid=u.id
                left join sync_client_survey survey on survey.id in  %(survey_ids)s
                left join client_survey_group_included_rel included on survey.id = included.survey_id
                left join client_survey_group_excluded_rel excluded on survey.id = excluded.survey_id
            where
                u.active='t' and
                u.id != 1
            group by u.id, survey.id
            having(
                (
                    survey.include_condition='or' and array_agg(rel.gid)&&array_remove(array_agg(included.group_id), NULL)
                    or
                    survey.include_condition='and' and array_agg(rel.gid)@>array_remove(array_agg(included.group_id), NULL)
                )
                and not(array_agg(excluded.group_id)&&array_agg(rel.gid))
            )
            order by u.login
        ''', {'survey_ids': tuple(ids)})

        for rel in cr.fetchall():
            res.setdefault(rel[0], []).append(rel[1])
        return res

    _columns = {
        'included_group_ids': fields.many2many('res.groups', 'client_survey_group_included_rel', 'survey_id', 'group_id', 'Included Groups'),
        'excluded_group_ids': fields.many2many('res.groups', 'client_survey_group_excluded_rel', 'survey_id', 'group_id', 'Excluded Groups'),
        'sync_server_id': fields.integer('Sync Server ID', select=1),
        'stat_by_users': fields.one2many('sync_client.survey.user', 'survey_id', 'Stats'),
        'users': fields.function(_get_users, method=1, type='one2many', relation='res.users', string='Matching Users'),
    }

    def get_surveys(self, cr, uid, context=None):
        if uid == 1:
            return []

        cr.execute('''
            select stat.last_choice, stat.id as stat_id, stat.last_displayed, stat.nb_displayed, survey.name, survey.name_fr, survey.url_en, survey.url_fr, survey.id as survey_id
            from
                sync_client_survey survey
                left join sync_client_survey_user stat on stat.survey_id = survey.id and stat.user_id = %(user_id)s
                left join client_survey_group_included_rel included on included.survey_id = survey.id
                left join client_survey_group_excluded_rel excluded on excluded.survey_id = survey.id
                left join res_groups_users_rel groups on groups.uid = %(user_id)s
            where
                survey.start_date < NOW() AND
                survey.end_date > NOW() AND
                survey.active='t'
            group by stat.last_choice, stat.id, stat.last_displayed, stat.nb_displayed, survey.name, survey.name_fr, survey.url_en, survey.url_fr, survey.id
            having (
                (
                    survey.include_condition='or' and array_remove(array_agg(included.group_id), NULL)&&array_agg(groups.gid)
                    or
                    survey.include_condition='and' and array_remove(array_agg(included.group_id), NULL) <@ array_agg(groups.gid)
                )

                AND not(array_agg(excluded.group_id)&&array_agg(groups.gid))
            )
        ''', {'user_id': uid}
        )

        result = []
        for x in cr.dictfetchall():
            if not x['stat_id']:
                x['stat_id'] = self.pool.get('sync_client.survey.user').create(cr, 1, {'survey_id': x['survey_id'], 'user_id': uid , 'last_displayed': time.strftime('%Y-%m-%d %H:%M:%S') , 'nb_displayed': 1})
                x['nb_displayed'] = 0
            else:
                if x['last_choice'] == 'never':
                    continue
                elif x['last_choice'] != 'goto':
                    cr.execute('update sync_client_survey_user set nb_displayed=nb_displayed+1 where id=%s', (x['stat_id'], ))
            if x['last_choice'] != 'goto':
                x['nb_displayed'] += 1

            result.append({'nb_displayed': x['nb_displayed'], 'name': x['name'], 'name_fr': x['name_fr'], 'url_en': x['url_en'], 'url_fr': x['url_fr'], 'id': x['survey_id'], 'stat_id': x['stat_id'], 'last_choice': x['last_choice']})

        return result

sync_client_survey()

class sync_client_survey_user(osv.osv):
    _name = 'sync_client.survey.user'
    _description = 'Stat by users'
    _columns = {
        'survey_id': fields.many2one('sync_client.survey', 'Survey', select=1),
        'user_id': fields.many2one('res.users', 'User', select=1),
        'last_displayed': fields.datetime('Last popup Date', select=1),
        'nb_displayed': fields.integer('# Display'),
        'last_choice': fields.selection([('goto', 'Go To'), ('never', "Don't Ask"), ('later', 'Ask me later')], 'Last Choice'),
    }

    def save_answer(self, cr, uid, answer, survey_id, stat_id, context=None):
        cr.execute('update sync_client_survey_user set last_displayed=now(), last_choice=%s where user_id=%s and survey_id=%s and id=%s', (answer, uid, survey_id, stat_id))

        field = {'goto': 'go_to', 'never': 'do_not_ask', 'later': 'answer_later'}.get(answer)
        if field:
            self.pool.get('sync_client.survey.user.detailed').create(cr, 1, {
                'survey_id': survey_id,
                'user_id': uid,
                field: True,
            }, context=context)
        return True

sync_client_survey_user()

class sync_client_survey_user_detailed(osv.osv):
    _name = 'sync_client.survey.user.detailed'
    _description = 'Detailed Stat by users'
    _columns = {
        'survey_id': fields.many2one('sync_client.survey', 'Survey', select=1),
        'user_id': fields.many2one('res.users', 'User', select=1),
        'popup_date': fields.datetime('Popup Date', select=1),
        'go_to': fields.boolean('Go to survey'),
        'answer_later': fields.boolean('Answer later'),
        'do_not_ask': fields.boolean('Do not ask me again '),
    }

    _defaults = {
        'popup_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'go_to': False,
        'answer_later': False,
        'do_not_ask': False,
    }

sync_client_survey_user_detailed()
