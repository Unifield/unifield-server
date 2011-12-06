ORDER_PRIORITY = [('emergency', 'Emergency'), 
                  ('normal', 'Normal'), 
                  ('priority', 'Priority'),]

ORDER_CATEGORY = [('medical', 'Medical'), 
                  ('log', 'Logistic'), 
                  ('food', 'Food'),
                  ('service', 'Service'), 
                  ('asset', 'Asset'), 
                  ('mixed', 'Mixed'),
                  ('other', 'Other')]

PURCHASE_ORDER_STATE_SELECTION = [('draft', 'Draft'),
                                  ('wait', 'Waiting'),
                                  ('confirmed', 'Waiting Approval'),
                                  ('approved', 'Approved'),
                                  ('except_picking', 'Shipping Exception'),
                                  ('except_invoice', 'Invoice Exception'),
                                  ('done', 'Done'),
                                  ('cancel', 'Cancelled'),
                                  ('rfq_sent', 'RfQ Sent'),
                                  ('rfq_updated', 'RfQ Updated'),
                                  #('rfq_done', 'RfQ Done'),
                                  ]

import purchase
import report
