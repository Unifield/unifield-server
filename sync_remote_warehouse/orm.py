from osv import osv, fields, orm

need_to_push = orm.orm.need_to_push

def need_to_push_usb(self, cr, uid, ids, included_fields, sync_field='sync_date', context=None):
        """
        Customisation for need_to_push in sync_client/orm.py for remote warehouse module.
        If sync_field is not usb_sync_date, return result of original function.
        Otherwise perform custom USB functionality:
        
        Check if records need to be pushed to the next USB synchronization process
        or not.
        
        One of these conditions need to match:
            - Last modification > clone_date
            - sync_date > clone_date
        
        ~ AND ~
        
        One of these conditions needs to match: 
            - usb_sync_date < last_modification
            - usb_sync_date < sync_date
            - usb_sync_date is not set
            - record is deleted
            - watched fields are present in modified fields

        Note: sync_date field can be changed to other field using parameter sync_field

        Return type:
            - If a list of ids is given, it returns a list of filtered ids.
            - If an id is given, it returns the id itself or False it the
              record doesn't need to be pushed.

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of the ids of the records to read
        :param included_field: fields list that have been modified
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return: list of ids that need to be pushed (or False for per record call)
        """
        
        context = context or {}
        if sync_field != 'usb_sync_date':
            return need_to_push(self, cr, uid, ids, included_fields, sync_field, context)
                
        clone_date = self.pool.get('sync.client.entity').get_entity(cr, uid, context).clone_date
                
        def clean_included_fields(included_fields):
            if not included_fields: return []
            result = [field.split('/')[0] for field in included_fields]
            result.pop(result.index('id'))
            return result

        result_iterable = hasattr(ids, '__iter__')
        if not result_iterable: ids = [ids]
        ids = filter(None, ids)
        if not ids: return ids if result_iterable else False
        
        # Pre-filter data where sync_date < last_modification OR sync_date IS NULL
        cr.execute("""\
SELECT id
    FROM ir_model_data
    WHERE module = 'sd' AND
          model = %%s AND
          res_id IN %%s AND
          (last_modification > '%(clone_date)s' OR sync_date > '%(clone_date)s') AND
          (usb_sync_date < last_modification OR usb_sync_date < sync_date OR usb_sync_date IS NULL)""" \
% {'clone_date':clone_date},
[self._name, tuple(ids)])
        data_ids = [row[0] for row in cr.fetchall()]
        if not data_ids: return [] if result_iterable else False
        # More accurate check: keep only the records that does not exists OR
        # there is no sync_date OR watch fields match
        watch_fields = set(clean_included_fields(included_fields))
        result = filter(
            lambda rec: (rec.is_deleted or not rec[sync_field] or \
                         watch_fields & set(self.get_last_modified_fields(cr, uid, rec.res_id, rec[sync_field], context=context))), \
            self.pool.get('ir.model.data').browse(cr, uid, data_ids, context=context) )
        if result_iterable:
            return map(lambda rec:rec.res_id, result)
        else:
            return bool(result)
        
orm.orm.need_to_push = need_to_push_usb