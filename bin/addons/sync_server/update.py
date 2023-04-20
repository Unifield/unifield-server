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

from __future__ import with_statement

from osv import orm, osv
from osv import fields
import tools
from tools.translate import _
import pprint
pp = pprint.PrettyPrinter(indent=4)
import logging
from tools.safe_eval import safe_eval as eval
import threading
from sync_common import add_sdref_column, fancy_integer

class SavePullerCache(object):
    def __init__(self, model):
        self.__model__ = model
        self.__cache__ = []
        self.__lock__ = threading.Lock()

    def add(self, entity, updates):
        if not updates:
            return
        if isinstance(updates[0], orm.browse_record):
            update_ids = (x.id for x in updates)
        else:
            update_ids = tuple(updates)
        if isinstance(entity, orm.browse_record):
            entity_id = entity.id
        else:
            entity_id = entity
        with self.__lock__:
            self.__cache__.append( (entity_id, update_ids) )

    def merge(self, cr, uid, context=None):
        if not self.__cache__:
            return
        with self.__lock__:
            cache, self.__cache__ = self.__cache__, type(self.__cache__)()
        for entity_id, updates in cache:
            for update_id in updates:
                self.__model__.pool.get('sync.server.puller_logs').create(cr, uid, {
                    'update_id': update_id,
                    'entity_id': entity_id,
                }, context=context)
#            for update_id in updates:
#                try:
#                    todo[update_id].add( entity_id )
#                except KeyError:
#                    todo[update_id] = set([entity_id])
#        for id, entity_ids in todo.items():
#            puller_ids = [(0, 0, {'entity_id':x}) for x in entity_ids]
#            self.__model__.write(cr, uid, [id], {'puller_ids': puller_ids}, context)

class puller_ids_rel(osv.osv):
    _name = "sync.server.puller_logs"
    _rec_name = "entity_id"
    _table = 'sync_server_entity_rel'

    _logger = logging.getLogger('sync.server')

    _columns = {
        'update_id' : fields.many2one('sync.server.update',
                                      required=True, string="Update", select=1),
        'entity_id' : fields.many2one('sync.server.entity',
                                      required=True, string="Instance", select=1),
        'create_date' : fields.datetime('Pull Date'),
    }

    def create(self, cr, uid, vals, context=None):
        try:
            del vals['create_date']
        except KeyError:
            pass
        super(puller_ids_rel, self).create(cr, uid, vals, context=context)

    def _auto_init(self, cr, context=None):
        super(puller_ids_rel, self)._auto_init(cr, context)
        foreign_key_to_delete = [
            'sync_server_entity_rel_create_uid_fkey',
            'sync_server_entity_rel_entity_id_fkey',
            'sync_server_entity_rel_update_id_fkey',
            'sync_server_entity_rel_write_uid_fkey'
        ]
        for to_del in foreign_key_to_delete:
            cr.execute("SELECT conname FROM pg_constraint WHERE conname = %s", (to_del, ))
            if cr.fetchone():
                cr.execute("ALTER table sync_server_entity_rel DROP CONSTRAINT %s" % (to_del,))  # not_a_user_entry

    def init(self, cr):
        cr.execute("""\
SELECT column_name 
  FROM information_schema.columns 
  WHERE table_name=%s AND column_name='id';""", [self._table])
        if not cr.fetchone():
            self._logger.info("Migrate old relational table %s to OpenERP model" % self._table)
            cr.execute("""\
-- Fix bad column name of old table
ALTER TABLE %(table)s RENAME COLUMN "update_id" TO "real_entity_id";
ALTER TABLE %(table)s RENAME COLUMN "entity_id" TO "update_id";
ALTER TABLE %(table)s RENAME COLUMN "real_entity_id" TO "entity_id";
-- Drop constraint to permit storing multiple pull for a same update
ALTER TABLE %(table)s DROP CONSTRAINT %(table)s_entity_id_key;
-- Create column id
ALTER TABLE "public"."%(table)s" ADD COLUMN "id" INTEGER;
CREATE SEQUENCE "public"."%(table)s_id_seq";
UPDATE %(table)s SET id = nextval('"public"."%(table)s_id_seq"');
ALTER TABLE "public"."%(table)s"
  ALTER COLUMN "id" SET DEFAULT nextval('"public"."%(table)s_id_seq"');
ALTER TABLE "public"."%(table)s"
  ALTER COLUMN "id" SET NOT NULL;
ALTER TABLE "public"."%(table)s" ADD UNIQUE ("id");
ALTER TABLE "public"."%(table)s" DROP CONSTRAINT "%(table)s_id_key" RESTRICT;
ALTER TABLE "public"."%(table)s" ADD PRIMARY KEY ("id");""" % {'table':self._table})  # not_a_user_entry


class update(osv.osv):
    """
        States : to_send : need to be sent to the server or the server ack still not received
                 sended : Ack for this update received but session not ended
                 validated : ack for the session of the update received, this update can be deleted
    """
    _name = "sync.server.update"
    _rec_name = 'source'

    _logger = logging.getLogger('sync.server')

    def _get_puller_ids(self, cr, uid, ids, field_name, args, context=None):
        return {}.fromkeys(ids, '')

    def _src_puller_ids(self, cr, uid, obj, name, args, context=None):
        res = []
        server_entity_obj = self.pool.get('sync.server.entity')
        for arg in args:
            if len(arg) > 2 and arg[0] == 'fancy_puller_ids':
                if ';' not in arg[2]:
                    entity_id = server_entity_obj.search(cr, uid,
                                                         [('name', '=', arg[2])]) or None
                    if entity_id:
                        res.append(('puller_ids', '=', entity_id))
                else:
                    list_of_pullers = arg[2].split(';')
                    list_of_ids = server_entity_obj.search(cr, uid,
                                                           [('name', 'in', tuple(list_of_pullers))])
                    if list_of_ids:
                        res.append(('puller_ids', 'in', list_of_ids))
        return res

    _columns = {
        'source': fields.many2one('sync.server.entity', string="Source Instance", select=True),
        'owner': fields.many2one('sync.server.entity', string="Owner Instance", select=True),
        'model': fields.char('Model', size=128, readonly=True, select=True),
        'sdref': fields.char('SD ref', size=128, readonly=True, select=True),
        'session_id': fields.char('Session Id', size=128),
        'sequence': fields.integer('Sequence', select=True),
        'fancy_sequence' : fields.function(fancy_integer, method=True, string="Sequence", type='char', readonly=True),
        'version': fields.integer('Record Version'),
        'fancy_version' : fields.function(fancy_integer, method=True, string="Version", type='char', readonly=True),
        'rule_id': fields.many2one('sync_server.sync_rule','Generating Rule', readonly=True, ondelete='restrict', select=True),
        'fields': fields.text("Fields"),
        'values': fields.text("Values"),
        'create_date': fields.datetime('Synchro Date/Time', readonly=True,
                                       select=True),
        'puller_ids': fields.one2many('sync.server.puller_logs', 'update_id', string="Pulled by"),
        'fancy_puller_ids': fields.function(_get_puller_ids,
                                            fnct_search=_src_puller_ids, method=True,
                                            string="Pulled by", type='char', store=False, readonly=True,
                                            internal=True),
        'is_deleted' : fields.boolean('Is deleted?', select=True),
        'force_recreation' : fields.boolean('Force record recreation'),
        'handle_priority': fields.boolean('Handle Priority'),
    }

    _order = 'create_date desc, id desc'

    _sql_constraints = [
        ('detect_duplicated_updates','UNIQUE (session_id, rule_id, sdref, owner)','This update is duplicated and has been ignored!'),
    ]

    @add_sdref_column
    def _auto_init(self, cr, context=None):
        cr.execute("""SELECT table_name FROM information_schema.tables WHERE table_name IN %s""",
                   [(puller_ids_rel._table, self._table)]);
        existing_tables = [row[0] for row in cr.fetchall()]
        if puller_ids_rel._table in existing_tables:
            cr.execute("""DELETE FROM %s WHERE update_id IN (SELECT id FROM %s WHERE rule_id IS NULL)""" % (puller_ids_rel._table, self._table))  # not_a_user_entry
        if self._table in existing_tables:
            cr.execute("""DELETE FROM %s WHERE rule_id IS NULL""" % self._table)  # not_a_user_entry
        super(update, self)._auto_init(cr, context=context)
        cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = 'sync_server_update_sequence_id_index'")
        if not cr.fetchone():
            cr.execute("CREATE INDEX sync_server_update_sequence_id_index on sync_server_update (sequence, id)")
        cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = 'sync_server_update_model_create_date_id_index'")
        if not cr.fetchone():
            cr.execute("CREATE INDEX sync_server_update_model_create_date_id_index ON sync_server_update(model, create_date, id)")
        cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = 'sync_server_update_create_date_id_index'")
        if not cr.fetchone():
            cr.execute("CREATE INDEX sync_server_update_create_date_id_index ON sync_server_update(create_date, id)")

    def _save_puller(self, cr, uid, context=None):
        return True

    def search_web(self, cr, uid, args=None, offset=0, limit=None, order=None,
                   context=None, count=False):
        return self.exact_search_web(cr, uid, args, offset, limit,
                                     order, context=context, count=count)

    def search_with_puller_ids(self, cr, uid, args, puller_ids_arg, offset=0,
                               limit=None, order=None, count=False, context=None):
        '''
        in case some puller_ids are in the args, a special threament is
        required to merge the requests in one. This id done inside this method
        '''
        where_clause = ''
        query = self._where_calc(cr, uid, args, context=context)
        from_clause, where_clause, where_clause_params = query.get_sql()
        if where_clause:
            where_clause = ''.join((' AND ', where_clause))

        final_params = []
        # DISTINCT is needed because we may enter puller_ids can contain
        # mre than one id, and then an update could be more than one time
        # in the results
        if count:
            final_query = "SELECT count(DISTINCT sync_server_update.id) "
        else:
            final_query = """SELECT DISTINCT sync_server_update.id """

        order_by=''
        if not count:
            if order != 'NO_ORDER':
                order = order or self._order
                if order:
                    order_by = ' ORDER BY %s.%s' % (self._table, order)
            if order:
                # because of the DISTINCT, to be able to order, table column to
                # order is needed in the select
                order_column = '%s.%s' % (self._table, order.split(' ')[0])
                final_query = '%s, %s ' % (final_query, order_column)

        final_query += """FROM sync_server_update INNER JOIN sync_server_entity_rel ON
        sync_server_update.id=sync_server_entity_rel.update_id
        WHERE sync_server_entity_rel.entity_id IN %s"""
        final_params.extend([tuple(puller_ids_arg[0][2])])
        final_params.extend(where_clause_params)
        if not count:
            final_query = final_query + where_clause + order_by + ' LIMIT %s OFFSET %s'
            final_params += [limit,offset]
        else:
            final_query += where_clause

        cr.execute(final_query, final_params)
        if count:
            result = cr.fetchone()
            return result[0] or 0
        return [x[0] for x in cr.fetchall()]

    def search(self, cr, uid, args=None, offset=0, limit=None, order=None, context=None, count=False):
        '''
        if there is fancy_puller_ids search parameter, do corresponding special
        treatmentwhere_params = []
        if not, do normal search
        '''
        new_args = []
        puller_ids_arg = False
        if args:
            for sub_domain in args:
                if sub_domain[0] == 'fancy_puller_ids':
                    puller_ids_arg = self._src_puller_ids(cr, uid, None, None, args)
                else:
                    new_args.append(sub_domain)
        if puller_ids_arg and len(puller_ids_arg[0])>2:
            return self.search_with_puller_ids(cr, uid, new_args,
                                               puller_ids_arg, offset, limit, order, count, context)

        return super(update, self).search(cr, uid, new_args, offset, limit,
                                          order, context=context, count=count)

    def unfold_package(self, cr, uid, entity, packet, context=None):
        """
            Called by receive_package() when client instance try to push its updates.

            @param cr : cr
            @param uid : uid
            @param entity : browse_record(sync.server.entity) : client instance entity
            @param packet : dict : update format packet.
                    Please see sync_server.sync_server.receive_package to get the full documentation
                    of the format.
            @param context : context

            @return : True or raise an error
        """
        self._logger.info("::::::::[%s] is pushing %s updates + %s delete" % (entity.name, len(packet['load']), len(packet['unload'])))
        def safe_create(data):
            cr.execute("SAVEPOINT update_creation")
            try:
                return self.create(cr, uid, data, context=context)
            except:
                cr.execute("ROLLBACK TO SAVEPOINT update_creation")
            else:
                cr.execute("RELEASE SAVEPOINT update_creation")
            return None

        self.pool.get('sync.server.entity').set_activity(cr, uid, entity, _('Pushing updates...'))

        normal_updates_count = 0
        for update in packet['load']:
            # Try to detect old packet type and raise an error
            assert 'owner' in update, "Packet field 'owner' absent"
            # Get the id of the owner or 0 if absent from sync.server.entity list
            owner = self.pool.get('sync.server.entity').search(cr, uid,
                                                               [('name','=',update['owner'])])
            owner = owner[0] if owner else False

            if safe_create({
                'session_id': packet['session_id'],
                'rule_id': packet['rule_id'],
                'source': entity.id,
                'model': packet['model'],
                'sdref' : update['sdref'],
                'version': update['version'],
                'fields': packet['fields'],
                'values': update['values'],
                'owner': owner,
                'handle_priority': update['handle_priority'],
                'force_recreation' : update['force_recreation'],
            }):
                normal_updates_count += 1

        delete_updates_count = 0
        for sdref in packet['unload']:
            if safe_create({
                'source': entity.id,
                'model': packet['model'],
                'session_id': packet['session_id'],
                'rule_id': packet['rule_id'],
                'sdref' : sdref,
                'is_deleted' : True,
            }):
                delete_updates_count += 1

        self._logger.info("::::::::[%s] Inserted %d new updates: %d normal(s) and %d delete(s)"
                          % (entity.name, (normal_updates_count+delete_updates_count), normal_updates_count, delete_updates_count))
        return True

    def confirm_updates(self, cr, uid, entity, session_id, context=None):
        """
            Called by confirm_update during client instance push process. It set a unique sequence number for all the sent packages.

            @param cr : cr
            @param uid : uid
            @param entity : browse_record(sync.server.entity) : client instance entity
            @param session_id : string : the synchronization session_id given at the beginning of the session by get_model_sync.
            @param context : context

            @return : tuple(a, b)
                a : boolean : is True is if the call is succesfull, False otherwise
                b : int : sequence number given
        """
        self._logger.info("::::::::[%s] Data Push :: Confirming updates session: %s" % (entity.name, session_id))
        self.pool.get('sync.server.entity').set_activity(cr, uid, entity, _('Confirm updates...'))

        has_updates = self.search_exists(cr, uid, [('session_id', '=', session_id), ('source', '=', entity.id), ('sequence', '=', False)], context=context)
        sequence = False
        nb_updates = 0
        if has_updates:
            sequence = self._get_next_sequence(cr, uid, context=context)
            cr.execute('''update sync_server_update set sequence=%s where session_id=%s and source=%s and sequence is null''', (sequence, session_id, entity.id))
            nb_updates = cr.rowcount
        self._logger.info("::::::::[%s] Data Push :: Number of data pushed: %d" % (entity.name, nb_updates))
        if sequence:
            self._logger.info("::::::::[%s] Data Push :: New server's sequence number: %s" % (entity.name, sequence))
        return (True, sequence)

    def _get_next_sequence(self, cr, uid, context=None):
        """
            Get a unique sequence number for the next sequence id
            @param cr : cr
            @param uid : uid
            @param context : context

            @return : int : sequence number
        """
        return int(self.pool.get('ir.sequence').get(cr, uid, 'sync.server.update'))

    def get_last_sequence(self, cr, uid, context=None):
        """
            Get the id of the last sequence number in the database
            @param cr : cr
            @param uid : uid
            @param context : context

            @return : int : sequence number or 0 if no update exists
        """
        ids = self.search(cr, uid, [('sequence', '!=', 0)], order="sequence desc, id desc", limit=1, context=context)
        if not ids:
            return 0
        seq = self.browse(cr, uid, ids, context=context)[0].sequence
        return seq

    def get_update_to_send(self,cr, uid, entity, update_ids, recover=False, context=None):
        """
            Called by get_package during the client instance pull process.
            Return a list of browse_record with only the updates that really need to be send to the client.
            It filter according to the rules:
             - rule's directionality is 'up' and update source is a child of entity
             - rule's directionality is 'down' and update source is an ancestor of entity
             - rule's directionality is 'bidirectional' (synchronize every where)
             - rule's directionality is 'bi-private': only the ancestors of update's owner field value
               are allowed to get the update.
            Then, it checks the groups.

            @param cr : cr
            @param uid : uid
            @param entity : browse_record(sync.server.entity) : client instance entity
            @param update_ids : list of update ids
            @param recover : flag : if set to True, update of the same source than the entity who try to pull
                are sent to the entity. Default is False.
            @param context : context

            @return : list of browse record of the updates to send
        """
        update_to_send = []
        ancestor = self.pool.get('sync.server.entity')._get_ancestor(cr, uid, entity.id, context=context)
        children = self.pool.get('sync.server.entity')._get_all_children(cr, uid, entity.id, context=context)
        for update in self.browse(cr, uid, update_ids, context=context):
            if not update.rule_id:
                continue
            if update.rule_id.direction == 'bi-private':
                if update.is_deleted:
                    privates = [entity.id]
                elif not update.owner:
                    privates = []
                else:
                    privates = self.pool.get('sync.server.entity')._get_ancestor(cr, uid, update.owner.id, context=context) + \
                        [update.owner.id]

            elif update.rule_id.direction == 'mission-private' and update.owner:
                privates = [x for x in
                            self.pool.get('sync.server.entity')._get_ancestor(cr, uid, update.owner.id, context=context) +
                            [update.owner.id] +
                            self.pool.get('sync.server.entity')._get_all_children(cr, uid, update.owner.id, context=context)
                            if x != update.source.id
                            ]
            else:
                privates = []
            if (update.rule_id.direction == 'up' and update.source.id in children) or \
               (update.rule_id.direction == 'down' and update.source.id in ancestor) or \
               (update.rule_id.direction == 'bidirectional') or \
               (entity.id in privates) or \
               (recover and entity.id == update.source.id):

                source_rules_ids = self.pool.get('sync_server.sync_rule')._get_groups_per_rule(cr, uid, update.source, context)
                s_group = source_rules_ids.get(update.rule_id.id, [])
                if any(group.id in s_group for group in entity.group_ids):
                    update_to_send.append(update)

        return update_to_send

    def get_package(self, cr, uid, entity, last_seq, offset, max_size, max_seq, recover=False, init_sync=False, context=None):
        """
            Called by XML RPC get_update method to give a list of updates to pull to the client instance.

            With optimization, SQL requests to search are made to avoid extra time to find updates.
            The updates are filtered and truncated before being sent to the client.

            @param cr : cr
            @param uid : uid
            @param entity : browse_record(sync.server.entity) : client instance entity
            @param last_seq : integer : Last sequence of update receive succefully in the previous pull session. 
            @param offset : integer : Number of record receive after the last_seq
            @param max_size : integer : The number of record max per packet. 
            @param max_seq : interger : The sequence max that the update the sync server send to the client in get_max_sequence, to tell the server don't send me
                    newer update then the one already their when the pull session start.
            @param recover : flag : If set to True, will recover self-owned package too.
            @param context : context

            @return :
                    Please see sync_server.sync_server.receive_package to get the full documentation
                    of the format.
                     - None when no update need to be sent
                     - A dict that format a packet for the client
        """
        self.pool.get('sync.server.entity').set_activity(cr, uid, entity, _('Pulling updates...'))
        top = entity
        while top.parent_id:
            top = top.parent_id
        tree_ids = self.pool.get('sync.server.entity')._get_all_children(cr, uid, top.id, context=context)
        if top.id not in tree_ids:
            tree_ids.append(top.id)
        tree_ids = [x for x in tree_ids if x!=entity.id]
        if not tree_ids:
            tree_ids = [0]
        tree_str = ','.join(map(str, tree_ids))
        rules = self.pool.get('sync_server.sync_rule')._compute_rules_to_receive(cr, uid, entity, context)
        if not rules:
            return None

        if not recover and init_sync:
            # first sync get only master data
            cr.execute("select id from sync_server_sync_rule where id in (" + ','.join(map(str, rules)) + ") and master_data='t'")  # not_a_user_entry
            rules = [x[0] for x in cr.fetchall()]

        base_query = " ".join(("""SELECT "sync_server_update".id FROM "sync_server_update" INNER JOIN sync_server_sync_rule ON sync_server_sync_rule.id = rule_id WHERE""",
                               "sync_server_update.rule_id IN (" + ','.join(map(str, rules)) + ")",
                               "AND sync_server_update.sequence > %s AND sync_server_update.sequence <= %s""" % (last_seq, max_seq)))

        ancestor = self.pool.get('sync.server.entity')._get_ancestor(cr, uid, entity.id, context=context)
        children = self.pool.get('sync.server.entity')._get_all_children(cr, uid, entity.id, context=context)

        # We filter out the updates that have nothing to do with the entity that is synchronizing
        filters = []
        if children:
            filters.append("direction = 'up' AND source IN (" + (','.join(map(str,children))) + ")")
        if ancestor:
            filters.append("direction = 'down' AND source IN (" + (','.join(map(str,ancestor))) + ")")
        filters.append("direction = 'bidirectional'")
        if recover:
            filters.append("source = %s" % (entity.id, ))
        filters.append("direction = 'bi-private' AND (is_deleted = 't' OR owner IN (" + (','.join(map(str, children + [entity.id]))) + "))")
        filters.append("direction = 'mission-private' AND source != " + str(entity.id) + " AND owner IN (" + (','.join(map(str, ancestor + children + [entity.id]))) + ")")
        base_query += ' AND ((' + ') OR ('.join(filters) + '))'

        ## Recover add own client updates to the list
        if not recover:
            base_query += " AND sync_server_update.source in (%s)" % (tree_str,)

        base_query += " AND sync_server_update.id > %s ORDER BY id ASC, sequence ASC OFFSET %s LIMIT %s"

        ## Search first update which is "master", then find next updates to send
        ids = []

        updates_to_send, updates_master = [], []
        offset_increment = 0
        packet_size = 0

        self._logger.info("::::::::[%s] Data pull get package:: init sync = %s, last_seq = %s, max_seq = %s, offset = %s, max_size = %s" % (entity.name, init_sync, last_seq, max_seq, '/'.join(map(str, offset)), max_size))

        while not ids or packet_size < max_size:
            cr.execute(base_query, (offset[0], offset[1], max_size))
            ids = map(lambda x:x[0], cr.fetchall())
            if not ids:
                break
            for update in self.get_update_to_send(cr, uid, entity, ids, recover, context):
                # There is no more room left in the packet. We have to quit. The next
                #  updates will be retrieved later.
                if packet_size >= max_size:
                    ids = ids[:ids.index(update.id)]
                    break

                # If this update is exactly the same as the previous one, we can pack
                #  them together because they can be executed together. Here we pack them
                #  if they behave the same way (same model, same rule, same source,
                #  same sequence, update type)
                if not updates_master or updates_master[-1].model != update.model or \
                        updates_master[-1].rule_id.id != update.rule_id.id or \
                        updates_master[-1].source.id != update.source.id or \
                        updates_master[-1].sequence != update.sequence or \
                        updates_master[-1].is_deleted != update.is_deleted:
                    updates_master.append(update)
                    updates_to_send.append([update])
                else:
                    updates_to_send[-1].append(update)

                packet_size += 1

            offset = (offset[0], offset[1]+len(ids))
            offset_increment += len(ids)

        if not updates_to_send:
            self._logger.info("::::::::[%s] No (more) update to send" % (entity.name,))
            return None

        # Point of no return
        #for update_to_send in updates_to_send:
            #self._cache_pullers.add(entity, update_to_send)
        for updates_by_type in updates_to_send:
            for update in iter(updates_by_type):
                self.pool.get('sync.server.puller_logs').create(cr, 1, {
                    'update_id': update.id,
                    'entity_id': entity.id,
                }, context=context)

        data_packages = []

        # We want to return all the updates we have found so far
        for update_master, update_to_send in zip(updates_master, updates_to_send):

            ## Package template
            data = {
                'model' : update_master.model,
                'source_name' : update_master.source.name,
                'sequence' : update_master.sequence,
                'rule' : update_master.rule_id.sequence_number,
                'offset' : (offset[0], offset_increment),
                'update_id': update_to_send[-1].id
            }

            ## Process & Push all updates in the packet
            if update_master.is_deleted:
                data['unload'] = [update.sdref for update in update_to_send]
                data['type'] = 'delete'
            else:
                complete_fields, forced_values = self.get_additional_forced_field(update_master)
                data.update({
                    'fields' : tools.ustr(complete_fields),
                    'fallback_values' : update_master.rule_id.fallback_values,
                    'load' : [],
                    'type' : 'import',
                })
                for update in update_to_send:
                    values = dict(zip(complete_fields[:len(update.values)], eval(update.values)) + \
                                  forced_values.items())
                    data['load'].append({
                        'sdref' : update.sdref,
                        'version' : update.version,
                        'values' : tools.ustr([values[k] for k in complete_fields]),
                        'owner_name' : update.owner.name if update.owner else '',
                        'force_recreation' : update.force_recreation,
                        'handle_priority' : update.handle_priority,
                    })

            data_packages.append(data)

        # Just shorten the log into one line
        self._logger.info("::::::::[%s] Data pull :: %s updates" % (entity.name, sum(map(lambda x : len(x.get('unload', [])) + len(x.get('load', [])), data_packages))))
        return data_packages


    def get_additional_forced_field(self, update):
        fields = eval(update.fields)
        forced_values = eval(update.rule_id.forced_values or '{}')
        if forced_values:
            fields += list(set(forced_values.keys()) - set(fields))
            obj = self.pool.get(update.model)
            inherit_fields = [(item[0], item[1][2]) for item in obj._inherit_fields.items()]
            columns = dict(inherit_fields + \
                           obj._columns.items())
            for k, v in forced_values.items():
                if columns[k]._type == 'boolean':
                    forced_values[k] = unicode(v)
        return fields, forced_values

update()
puller_ids_rel()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
