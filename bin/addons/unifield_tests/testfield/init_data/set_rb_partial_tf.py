from oerplib import OERP
import time
import os

"""
Set data for testfield supply ct1 / ct2
"""


DB_PREFIX = ''
SRV_ADDRESS = '%s.rb.unifielf.org' % DB_PREFIX
XMLRPC_PORT = ''
UNIFIELD_ADMIN = ''
UNIFIELD_PASSWORD = ''

if os.path.exists('credentials.py'):
    execfile('credentials.py')

oerp = OERP(server=SRV_ADDRESS, protocol='xmlrpc', port=XMLRPC_PORT, timeout=3600, version='6.0')
l = oerp.login(UNIFIELD_ADMIN, UNIFIELD_PASSWORD, '%s_SYNC_SERVER' % DB_PREFIX)
ids = oerp.get('sync.server.entity').search([])
oerp.get('sync.server.entity').write(ids, {'user_id': 1})


sync_needed = False
l = oerp.login(UNIFIELD_ADMIN, UNIFIELD_PASSWORD, '%s_HQ1C1' % DB_PREFIX)
prod_o = oerp.get('product.product')
if not prod_o.search([('default_code', '=', 'AZAZA')]):
    print 'Create Prod AZAZA'
    sync_needed = True
    oerp.get('product.product').create({
        'default_code': 'AZAZA',
        'name': 'Product test',
        'procure_method': 'make_to_order',
        'international_status': 1,
        'nomen_manda_0': 5,
        'nomen_manda_1': 9,
        'nomen_manda_2': 23,
        'nomen_manda_3': 483,
    })
p_ids = oerp.get('res.partner').search([('name', '=', 'ESC'), ('active', 'in', ['t', 'f'])])
if p_ids:
    print 'Update Partner'
    sync_needed = True
    oerp.get('res.partner').write(p_ids, {'active': True, 'name': 'MSF supply'})

loc_o = oerp.get('stock.location')
loc_ids = loc_o.search([('name', '=', 'LOG')])
prod_o = oerp.get('product.product')
p_ids = prod_o.search([('default_code', '=', 'ADAPCABL1S-')])
inv_o = oerp.get('stock.inventory')
inv_id = inv_o.create({
    'name': 'inv %s' % time.time(),
    'inventory_line_id': [(0, 0, {'location_id': loc_ids[0], 'product_id': p_ids[0], 'product_uom': 1, 'product_qty': 1000, 'reason_type_id': 12})],
})
inv_o.action_confirm([inv_id])
inv_o.action_done([inv_id])

po_o = oerp.get('purchase.order')
po_ids = po_o.search([('state', '=', 'draft')])
if po_ids:
    print "HQ1C1 reset po"
    po_o.write(po_ids, {'delivery_requested_date': '2030-01-01'})

conn_manager = oerp.get('sync.client.sync_server_connection')
conn_ids = conn_manager.search([])
conn_manager.disconnect()
conn_manager.write(conn_ids, {'password': UNIFIELD_PASSWORD, 'login': UNIFIELD_ADMIN})
conn_manager.connect()
if sync_needed:
    oerp.get('sync.client.entity').sync()




l = oerp.login(UNIFIELD_ADMIN, UNIFIELD_PASSWORD, '%s_HQ1C1P1' % DB_PREFIX)
conn_manager = oerp.get('sync.client.sync_server_connection')
conn_ids = conn_manager.search([])
conn_manager.disconnect()
conn_manager.write(conn_ids, {'password': UNIFIELD_PASSWORD, 'login': UNIFIELD_ADMIN})
conn_manager.connect()
if sync_needed:
    oerp.get('sync.client.entity').sync()

ext_name = 'Ext CU Sara'
loc_o = oerp.get('stock.location')
if not loc_o.search([('name', '=', ext_name)]):
    print 'Create Loc'
    stock_wiz = oerp.get('stock.location.configuration.wizard')
    w_id = stock_wiz.create({'location_usage': 'consumption_unit', 'location_type': 'customer', 'location_name': ext_name})
    stock_wiz.confirm_creation(w_id)

loc_ids = loc_o.search([('name', '=', 'LOG')])
prod_o = oerp.get('product.product')
p_ids = prod_o.search([('default_code', '=', 'ADAPCABL2S-')])
inv_o = oerp.get('stock.inventory')
inv_id = inv_o.create({
    'name': 'inv %s' % time.time(),
    'inventory_line_id': [(0, 0, {'location_id': loc_ids[0], 'product_id': p_ids[0], 'product_uom': 1, 'product_qty': 1000, 'reason_type_id': 12})],
})
inv_o.action_confirm([inv_id])
inv_o.action_done([inv_id])

po_o = oerp.get('purchase.order')
po_ids = po_o.search([('state', '=', 'draft')])
if po_ids:
    print "HQ1C1P1 reset po"
    po_o.write(po_ids, {'delivery_requested_date': '2030-01-01'})
