def migrate(cr, version):
    if not cr.table_exists('ir_module_module'):
        return

    cr.execute("update ir_module_module set state='uninstalled' where name ='base_report_designer'")
    return True

