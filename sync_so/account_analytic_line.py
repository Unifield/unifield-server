from osv import osv, fields

class account_analytic_line(osv.osv):
    _inherit = 'account.analytic.line'

    _columns = {
        'owner' : fields.char('Instance Owner', size=64),
    }

account_analytic_line()

