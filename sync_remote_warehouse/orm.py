from osv import osv, fields, orm

def usb_need_to_push(self, cr, uid, ids, context=None):
        """
        
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

        Return type:
            - If a list of ids is given, it returns a list of filtered ids.
            - If an id is given, it returns the id itself or False it the
              record doesn't need to be pushed.

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of the ids of the records to read
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :return: list of ids that need to be pushed (or False for per record call)

        """
        
        clone_date = self.pool.get('sync.client.entity').get_entity(cr, uid, context).clone_date
        
        result_iterable = hasattr(ids, '__iter__')
        if not result_iterable: ids = [ids]
        ids = filter(None, ids)
        if not ids: return ids if result_iterable else False
        
        # Optimization for not deleted records:
        # Filter data where sync_date < last_modification OR sync_date IS NULL        
        cr.execute("""\
        SELECT res_id
            FROM ir_model_data
            WHERE module = 'sd' AND
                  model = %%s AND
                  res_id IN %%s AND
                  (last_modification > '%(clone_date)s' OR sync_date > '%(clone_date)s') AND
                  (usb_sync_date < last_modification OR usb_sync_date < sync_date OR usb_sync_date IS NULL)""" % {'clone_date' : clone_date},
        [self._name, tuple(ids)])
        
        result = [row[0] for row in cr.fetchall()]
        return result if result_iterable else len(result) > 0

orm.orm.usb_need_to_push = usb_need_to_push