<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>MSFUser</Author>
  <LastAuthor>MSFUser</LastAuthor>
  <Created>2012-06-18T15:46:09Z</Created>
  <Company>Medecins Sans Frontieres</Company>
  <Version>11.9999</Version>
 </DocumentProperties>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>13170</WindowHeight>
  <WindowWidth>19020</WindowWidth>
  <WindowTopX>120</WindowTopX>
  <WindowTopY>60</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
<Styles>
    <Style ss:ID="header">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Protection />
    </Style>
    <Style ss:ID="line_wb">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Protection ss:Protected="0" />
    </Style>
    <Style ss:ID="line">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Protection ss:Protected="0" />
    </Style>
  <Style ss:ID="short_date">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="Short Date"/>
   <Protection ss:Protected="0" />
  </Style>
</Styles>
## ==================================== we loop over the purchase_order "objects" == purchase_order  ====================================================
% for o in objects:
<ss:Worksheet ss:Name="${"%s"%(o.name.split('/')[-1] or 'Sheet1')|x}" ss:Protected="1">
    ## definition of the columns' size
<% max_ad_lines = maxADLines(o) %>
<% nb_of_columns = 17 %>
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="300" />
% for x in range(2,nb_of_columns - 1):
<Column ss:AutoFitWidth="1" ss:Width="60" />
% endfor
<Column ss:AutoFitWidth="1" ss:Width="250" />

## we loop over the purchase_order_line "%s"%po_name.split('/')[-1])

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Order Reference*')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.name or ''|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Order Type')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(o, 'order_type')|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Order Category')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(o, 'categ')|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Creation Date')}</Data></Cell>
        % if isDate(o.date_order):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.date_order|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Supplier Reference')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.partner_ref or ''|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Details')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.details or ''|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Stock Take Date')}</Data></Cell>
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.stock_take_date|n}T00:00:00.000</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Delivery Requested Date')}</Data></Cell>
        % if isDate(o.delivery_requested_date):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.delivery_requested_date|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Transport mode')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(o, 'transport_type') or ''|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('RTS Date')}</Data></Cell>
        % if isDate(o.ready_to_ship_date):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.ready_to_ship_date|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Delivery address name')}</Data></Cell>
        % if o.order_type == 'direct':
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getContactName(o.dest_partner_id.id)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.dest_address_id and o.dest_address_id.name or ''|x}</Data></Cell>
        % endif
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Delivery address')}</Data></Cell>
        % if o.order_type == 'direct':
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.dest_partner_id and o.dest_partner_id.name or ''|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getInstanceName()|x}</Data></Cell>
        % endif
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Customer address name')}</Data></Cell>
        % if o.order_type == 'direct':
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getInstanceAddress() or ''|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.customer_id and getCustomerAddress(o.customer_id.id) or ''|x}</Data></Cell>
        % endif
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Customer address')}</Data></Cell>
        % if o.order_type == 'direct':
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getInstanceName()|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.customer_id and o.customer_id.name or ''|x}</Data></Cell>
        % endif
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Shipment Date')}</Data></Cell>
        % if isDate(o.shipment_date):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.shipment_date|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Notes')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.notes or ''|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Origin')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.origin or ''|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Project Ref.')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.fnct_project_ref or ''|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Message ESC Header')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.message_esc or ''|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Sourcing group')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.related_sourcing_id and o.related_sourcing_id.name or ''|x}</Data></Cell>
    </Row>

    % if need_ad and o.analytic_distribution_id:
        <Row>
            <Cell ss:MergeDown="1" ss:StyleID="header" ><Data ss:Type="String">${_('Analytic Distribution')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Destination')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Cost Center')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('%')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Subtotal')}</Data></Cell>
            % for x in range(1, len(o.analytic_distribution_id.cost_center_lines)):
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Destination')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Cost Center')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('%')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Subtotal')}</Data></Cell>
            % endfor
        </Row>
        <Row>
        % for i, ccl in enumerate(o.analytic_distribution_id.cost_center_lines):
            <Cell ss:Index="${(i*4+2)|x}" ss:StyleID="line" ><Data ss:Type="String">${(ccl.destination_id.code or '')|x}</Data></Cell>
            <Cell ss:Index="${(i*4+3)|x}" ss:StyleID="line" ><Data ss:Type="String">${(ccl.analytic_id.code or '')|x}</Data></Cell>
            <Cell ss:Index="${(i*4+4)|x}" ss:StyleID="line" ><Data ss:Type="Number">${(ccl.percentage or 0.00)|x}</Data></Cell>
            <Cell ss:Index="${(i*4+5)|x}" ss:StyleID="line" ><Data ss:Type="Number">${((ccl.percentage/100.00)*o.amount_total or 0.00)|x}</Data></Cell>
        % endfor
        </Row>
    % else:
        <Row>
            <Cell ss:MergeDown="1" ss:StyleID="header" ><Data ss:Type="String">${_('Analytic Distribution')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Destination')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Cost Center')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('%')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Subtotal')}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:Index="2" ss:StyleID="line" />
            <Cell ss:Index="3" ss:StyleID="line" />
            <Cell ss:Index="4" ss:StyleID="line" />
            <Cell ss:Index="5" ss:StyleID="line" />
        </Row>
    % endif

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Line number')}</Data></Cell>    
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Ext. Ref.')}</Data></Cell>    
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Code*')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Description')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Qty*')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product UoM*')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Price Unit*')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Currency*')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Origin*')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Stock Take Date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Delivery requested date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Delivery confirmed date*')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Nomen Name')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Nomen Group')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Nomen Family')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Comment')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Notes')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Project Ref')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('ESC Message 1')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('ESC Message 2')}</Data></Cell>
        % if max_ad_lines:
            % for x in range(1, max_ad_lines+1):
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Destination')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Cost Center')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('%')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Subtotal')}</Data></Cell>
            % endfor
        % else:
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Destination')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Cost Center')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('%')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Subtotal')}</Data></Cell>
        % endif
    </Row>
    % for line in o.order_line:
        % if line.state != 'cancel' and line.state != 'cancel_r':
            <% len_cc_lines = line.analytic_distribution_id and len(line.analytic_distribution_id.cost_center_lines) or 0 %>
            <Row>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.line_number or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.external_ref or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id and line.product_id.default_code or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id and line.product_id.name or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.product_qty or 0.00)|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_uom.name or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.price_unit or 0.00)|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.pricelist_id.currency_id.name or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.origin or '')|x}</Data></Cell>
            <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.stock_take_date|n}T00:00:00.000</Data></Cell>
            % if isDate(line.date_planned):
            <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.date_planned|n}T00:00:00.000</Data></Cell>
            % elif isDate(o.delivery_requested_date):
            ## if the date does not exist in the line we take the one from the header
            <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.delivery_requested_date|n}T00:00:00.000</Data></Cell>
            % else:
            <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
            % endif
            % if isDate(line.confirmed_delivery_date):
            <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.confirmed_delivery_date|n}T00:00:00.000</Data></Cell>
            % elif isDate(o.delivery_confirmed_date):
            ## if the date does not exist in the line we take the one from the header
            <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.delivery_confirmed_date|n}T00:00:00.000</Data></Cell>
            % else:
            <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
            % endif
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.nomen_manda_0 and line.nomen_manda_0.name or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.nomen_manda_1 and line.nomen_manda_1.name or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.nomen_manda_2 and line.nomen_manda_2.name or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.comment or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.notes or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.fnct_project_ref or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
            % if need_ad:
                % if line.analytic_distribution_id:
                    % for ccl in line.analytic_distribution_id.cost_center_lines:
                <Cell ss:StyleID="line" ><Data ss:Type="String">${(ccl.destination_id.code or '')|x}</Data></Cell>
                <Cell ss:StyleID="line" ><Data ss:Type="String">${(ccl.analytic_id.code or '')|x}</Data></Cell>
                <Cell ss:StyleID="line" ><Data ss:Type="Number">${(ccl.percentage or 0.00)|x}</Data></Cell>
                <Cell ss:StyleID="line" ><Data ss:Type="Number">${((ccl.percentage/100.00) * line.price_subtotal or 0.00)|x}</Data></Cell>
                    % endfor
                    % for x in range(0, max_ad_lines-len_cc_lines):
                <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
                <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
                <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
                <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
                    % endfor
                % endif
            % else:
                <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
                <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
                <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
                <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
            % endif
            </Row>
        % endif
    % endfor
</Table>
<x:WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
    <ProtectObjects>True</ProtectObjects>
    <ProtectScenarios>True</ProtectScenarios>
    <EnableSelection>UnlockedCells</EnableSelection>
    <AllowInsertRows />
</x:WorksheetOptions>
</ss:Worksheet>
% endfor
</Workbook>
