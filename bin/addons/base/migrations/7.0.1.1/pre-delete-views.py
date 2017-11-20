def migrate(cr, version):
    if not cr.table_exists('ir_ui_view'):
        return

    cr.execute("update ir_module_module set state='uninstalled' where name='sale_override'")
    cr.execute("delete from ir_ui_view where id in (select res_id from ir_model_data where module='sale_override' and model='ir.ui.view')")
    cr.execute("update ir_module_module set state='to upgrade' where name='msf_button_access_rights'")

    # WKF
    cr.execute("delete from wkf_workitem where act_id in (select id from  wkf_activity  where wkf_id in (select id from wkf  where osv in ('purchase.order', 'sale.order', 'procurement.order')))")
    cr.execute("delete from wkf where osv in ('purchase.order', 'sale.order', 'procurement.order')")

    # set required values
    #cr.execute("update sync_client_message_received set rule_sequence = 0")
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
