<?xml version="1.0"?>
<data>
% for o in objects:
    <record model="purchase.order" key="name">
        <field name="name">${o.name or ''}</field>
        <field name="order_type">${getSel(o, 'order_type')}</field>
        <field name="categ">${getSel(o, 'categ')}</field>
        <field name="date_order">${o.date_order or ''}</field>
        <field name="partner_ref">${o.partner_ref or ''}</field>
        <field name="details">${o.details or ''}</field>
        <field name="delivery_requested_date">${o.delivery_requested_date or ''}</field>
        <field name="transport_type">${getSel(o, 'transport_type')}</field>
        <field name="ready_to_ship_date">${o.ready_to_ship_date or ''}</field>
        <field name="dest_address_id" key="name,parent.partner_id">
			<field name="name">${o.dest_address_id and o.dest_address_id.name or ''}</field>
			<field name="street">${o.dest_address_id and o.dest_address_id.street or ''}</field>
			<field name="street2">${o.dest_address_id and o.dest_address_id.street2 or ''}</field>
			<field name="zip">${o.dest_address_id and o.dest_address_id.zip or ''}</field>
			<field name="city">${o.dest_address_id and o.dest_address_id.city or ''}</field>
			<field name="country_id" key="name">
				<field name="name">${o.dest_address_id and o.dest_address_id.country_id and o.dest_address_id.country_id.name or ''}</field>
			</field>
        </field>
        <field name="shipment_date">${o.shipment_date}</field>
        <field name="notes">${o.notes or ''}</field>
        <field name="origin">${o.origin or ''}</field>
        <field name="project_ref">${o.project_ref or ''}</field>
        <field name="message_esc">${o.message_esc or ''}</field>
        <field name="">
        % for l in o.order_line:
			<record>
				<field name="line_number">${l.line_number or ''}</field>
				<field name="external_ref">${l.external_ref or ''}</field>
				<field name="product_id" key="default_code,name">
					<field name="product_code">${l.product_id and l.product_id.default_code or ''}</field>
					<field name="product_name">${l.product_id and l.product_id.name or ''}</field>
				</field>
				<field name="product_qty">${l.product_qty or 0.00}</field>
				<field name="product_uom" key="name">
					<field name="name">${l.product_uom and l.product_uom.name or ''}</field>
				</field>
				<field name="price_unit">${l.price_unit or ''}</field>
				<field name="currency_id" key="name">
					<field name="name">${l.currency_id and l.currency_id.name or ''}</field>
				</field>
				<field name="origin">${l.origin}</field>
				<field name="date_planned">${l.date_planned}</field>
				<field name="nomen_manda_0" key="name">
					<field name="name">${l.nomen_manda_0 and l.nomen_manda_0.name or ''}</field>
				</field>
				<field name="nomen_manda_1" key="name">
					<field name="name">${l.nomen_manda_1 and l.nomen_manda_1.name or ''}</field>
				</field>
				<field name="nomen_manda_2" key="name">
					<field name="name">${l.nomen_manda_2 and l.nomen_manda_2.name or ''}</field>
				</field>
				<field name="comment">${l.comment or ''}</field>
				<field name="notes">${l.notes or ''}</field>
				<field name="project_ref">${l.project_ref or ''}</field>
				<field name="message_esc1"></field>
				<field name="message_esc2"></field>
			</record>
        % endfor
        </field>
    </record>
    % endfor
</data>
