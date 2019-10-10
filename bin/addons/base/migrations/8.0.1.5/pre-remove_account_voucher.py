
def migrate(cr, version):
    if not cr.table_exists('ir_module_module'):
        return

    cr.execute("update ir_module_module set state='uninstalled' where name='account_voucher'")

    if not cr.table_exists('wkf'):
        return
    cr.execute("delete from wkf where osv='payment.order'")
    return True
