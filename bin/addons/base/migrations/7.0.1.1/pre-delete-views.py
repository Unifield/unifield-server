from tools import config
import os

def migrate(cr, version):
    if not cr.table_exists('ir_ui_view'):
        return

    cr.execute("update ir_module_module set state='uninstalled' where name='sale_override'")
    cr.execute("delete from ir_ui_view where id in (select res_id from ir_model_data where module='sale_override' and model='ir.ui.view')")
    cr.execute("delete from ir_ui_menu where id in (select res_id from ir_model_data where model='ir.ui.menu' and module='sale_override')")
    cr.execute("update ir_module_module set state='to upgrade' where name='msf_button_access_rights'")
    cr.execute("update ir_model_data set name=regexp_replace(name,'^sale_override_(.*)$', 'sale_\\1') where model='ir.model' and module='sd'")

    queries = os.path.join(config['root_path'], 'addons/base/migrations/7.0.1.1/update_ir_model_data_fields.sql')
    if os.path.exists(queries):
        with open(queries) as lines:
            for line in lines:
                if line:
                    cr.execute(line)

    # WKF
    cr.execute("delete from wkf_workitem where act_id in (select id from  wkf_activity  where wkf_id in (select id from wkf  where osv in ('purchase.order', 'sale.order', 'procurement.order')))")
    cr.execute("delete from wkf where osv in ('purchase.order', 'sale.order', 'procurement.order')")

    # set required values
    #cr.execute("update sync_client_message_received set rule_sequence = 0")
    cr.execute("update ir_ui_view set priority=2500+id where priority=250 and type='tree' and name like 'query.tree%'")
    cr.execute("update ir_ui_view set priority=2500+id where type='search' and name like 'query.search%'")
    cr.drop_index_if_exists('ir_ui_view', 'ir_ui_view_model_type_priority')
    cr.drop_constraint_if_exists('ir_ui_view', 'ir_ui_view_unique_view')
    cr.execute("create unique index ir_ui_view_model_type_priority on ir_ui_view(id)")
    cr.execute("alter table ir_ui_view add constraint ir_ui_view_unique_view unique(id)")

    if cr.column_exists('ir_ui_view', 'inherit_id'): 
        # set fake records to prevent resinstallion of constraints, deleted in msf_profile
        cr.execute("insert into ir_ui_view (name, model, type, arch, priority) values ('aaa', 'aaa', 'aaa', '', 5) returning id")
        new_id = cr.fetchone()[0]
        cr.execute("insert into ir_ui_view (name, model, type, arch, priority, inherit_id) values ('aaa', 'aaa', 'aaa', '', 5, %s)", (new_id,))
        cr.execute("insert into ir_ui_view (name, model, type, arch, priority, inherit_id) values ('aaa', 'aaa', 'aaa', '', 5, %s)", (new_id,))
    return True
