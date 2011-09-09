import logging
import rpc

FORMAT = '%(asctime)-15s %(name)s %(levelname)s: %(message)s'
logging.basicConfig(format=FORMAT)

connector = rpc.GzipXmlRPCConnector('localhost', 10070)
connector = rpc.NetRPCConnector('localhost', 8070)
connector = rpc.XmlRPCConnector('localhost', 10070)
connector = rpc.SecuredXmlRPCConnector('localhost', 10071)

connection = rpc.Connection(connector, 'server_test', 'admin', 'admin', 1)

Users = rpc.Object(connection, 'res.users')
admin = Users.read([1,2])

Currencies = rpc.Object(connection, 'res.currency')
all_cur_ids = Currencies.search([])
all_currencies = Currencies.read(all_cur_ids)

