ORDER_PRIORITY = [
	('emergency', 'Emergency'), 
	('normal', 'Normal'), 
	('priority', 'Priority'),
]

ORDER_CATEGORY = [
	('medical', 'Medical'),
	('log', 'Logistic'),
	('service', 'Service'),
	('transport', 'Transport'),
	('other', 'Other'),
]

PURCHASE_ORDER_LINE_STATE_SELECTION = [
	('draft', 'Draft'),
	('validated', 'Validated'),
	('sourced', 'Sourced'),
	('confirmed', 'Confirmed'),
	('done', 'Done'),
	('cancel', 'Cancelled'),
]

PURCHASE_ORDER_STATE_SELECTION = PURCHASE_ORDER_LINE_STATE_SELECTION


import purchase
import report
import wizard
