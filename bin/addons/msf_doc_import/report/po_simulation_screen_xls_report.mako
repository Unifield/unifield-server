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
    <Style ss:ID="line_change">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Interior ss:Color="#ff0000" ss:Pattern="Solid" />
        <Protection ss:Protected="0" />
    </Style>
    <Style ss:ID="line_change_short_date">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Interior ss:Color="#ff0000" ss:Pattern="Solid" />
        <NumberFormat ss:Format="Short Date" />
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
   <NumberFormat ss:Format="Short Date" />
   
   <Protection ss:Protected="0" />
  </Style>
</Styles>
% for o in objects:
<ss:Worksheet ss:Name="${"%s"%(o.order_id.name.split('/')[-1] or 'Sheet1')|x}" ss:Protected="0">
## definition of the columns' size
<% nb_of_columns = 17 %>
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="300" />
% for x in range(2,nb_of_columns - 1):
<Column ss:AutoFitWidth="1" ss:Width="60" />
% endfor
<Column ss:AutoFitWidth="1" ss:Width="250" />

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Order Reference')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.order_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Creation Date')}</Data></Cell>
        % if isDate(o.order_id.date_order):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${(o.order_id.date_order)|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ></Cell>
        % endif
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Destination Address')}</Data></Cell>
        <Cell ss:StyleID="line" ss:MergeAcross="2" ><Data ss:Type="String">${(o.in_dest_addr and obj_name_get('res.partner.address', o.in_dest_addr.id) or '')|x}</Data></Cell>
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Field name')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Original value')}</Data></Cell>
        <Cell ss:StyleID="header" ss:MergeAcross="1" ><Data ss:Type="String">${_('Imported value')}</Data></Cell>
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Supplier Reference')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.in_supplier_ref or '')|x}</Data></Cell>
        % if o.imp_supplier_ref != o.in_supplier_ref:
        <Cell ss:StyleID="line_change" ss:MergeAcross="1" ><Data ss:Type="String">${(o.imp_supplier_ref or '')|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ss:MergeAcross="1" ><Data ss:Type="String">${(o.imp_supplier_ref or '')|x}</Data></Cell>
        % endif
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Transport Mode')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(o, 'in_transport_mode') or ''|x}</Data></Cell>
        % if o.imp_transport_mode != o.in_transport_mode:
        <Cell ss:StyleID="line_change" ss:MergeAcross="1" ><Data ss:Type="String">${getSel(o, 'imp_transport_mode') or ''|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ss:MergeAcross="1" ><Data ss:Type="String">${getSel(o, 'imp_transport_mode')or ''|x}</Data></Cell>
        % endif
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('RTS Date')}</Data></Cell>
        % if isDate(o.in_ready_to_ship_date):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${(o.in_ready_to_ship_date)|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ></Cell>
        % endif
        % if isDate(o.imp_ready_to_ship_date) and o.imp_ready_to_ship_date != o.in_ready_to_ship_date:
        <Cell ss:StyleID="line_change_short_date" ss:MergeAcross="1" ><Data ss:Type="DateTime">${(o.imp_ready_to_ship_date)|n}T00:00:00.000</Data></Cell>
        % elif isDate(o.imp_ready_to_ship_date):
        <Cell ss:StyleID="short_date" ss:MergeAcross="1" ><Data ss:Type="DateTime">${(o.imp_ready_to_ship_date)|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ss:MergeAcross="1" ></Cell>
        % endif
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Shipment Date')}</Data></Cell>
        % if isDate(o.in_shipment_date):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${(o.in_shipment_date)|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ></Cell>
        % endif
        % if isDate(o.imp_shipment_date) and o.imp_shipment_date != o.in_shipment_date:
        <Cell ss:StyleID="line_change_short_date" ss:MergeAcross="1" ><Data ss:Type="DateTime">${(o.imp_shipment_date)|n}T00:00:00.000</Data></Cell>
        % elif isDate(o.imp_shipment_date):
        <Cell ss:StyleID="short_date" ss:MergeAcross="1" ><Data ss:Type="DateTime">${(o.imp_shipment_date)|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ss:MergeAcross="1" ></Cell>
        % endif
    </Row>

    <Row></Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Untaxed Amount')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(o.in_amount_untaxed or 0.00)|x}</Data></Cell>
        % if o.imp_amount_untaxed != o.in_amount_untaxed:
        <Cell ss:StyleID="line_change" ss:MergeAcross="1" ><Data ss:Type="Number">${(o.imp_amount_untaxed or 0.00)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ss:MergeAcross="1" ><Data ss:Type="Number">${(o.imp_amount_untaxed or 0.00)|x}</Data></Cell>
        % endif
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Total')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(o.in_amount_total or 0.00)|x}</Data></Cell>
        % if o.imp_amount_total != o.in_amount_total:
        <Cell ss:StyleID="line_change" ss:MergeAcross="1" ><Data ss:Type="Number">${(o.imp_amount_total or 0.00)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ss:MergeAcross="1" ><Data ss:Type="Number">${(o.imp_amount_total or 0.00)|x}</Data></Cell>
        % endif
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Total Incl. Transport:')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(o.in_total_price_include_transport or 0.00)|x}</Data></Cell>
        % if o.in_total_price_include_transport != o.imp_total_price_include_transport:
        <Cell ss:StyleID="line_change" ss:MergeAcross="1" ><Data ss:Type="Number">${(o.imp_total_price_include_transport or 0.00)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ss:MergeAcross="1" ><Data ss:Type="Number">${(o.imp_total_price_include_transport or 0.00)|x}</Data></Cell>
        % endif
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Discrepancy')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number"></Data></Cell>
        % if o.amount_discrepancy != 0.00:
        <Cell ss:StyleID="line_change" ss:MergeAcross="1" ><Data ss:Type="Number">${(o.amount_discrepancy or 0.00)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ss:MergeAcross="1" ><Data ss:Type="Number">${(o.amount_discrepancy or 0.00)|x}</Data></Cell>
        % endif
    </Row>

    <Row></Row>

    <Row>
        <Cell ss:StyleID="header" ss:MergeAcross="3" ><Data ss:Type="String">${_('Header Notes')}</Data></Cell>
    </Row>

    <Row>
        <Cell ss:StyleID="line" ss:MergeAcross="3" ><Data ss:Type="String">${(o.in_notes or '')|x}</Data></Cell>
    </Row>

    <Row>
        <Cell ss:StyleID="header" ss:MergeAcross="3" ><Data ss:Type="String">${_('Message ESC Header')}</Data></Cell>
    </Row>

    <Row>
        <Cell ss:StyleID="line" ss:MergeAcross="3" ><Data ss:Type="String">${(o.imp_message_esc or '')|x}</Data></Cell>
    </Row>

    <Row></Row>
    
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Nomenclature')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Comment')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Qty')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('UoM')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Delivery Requested Date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Delivery Confirmed Date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Price Unit')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Currency')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Line Number')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('CHG')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Qty')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Price unit')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Discrepancy')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Currency')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Delivery Requested Date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Delivery Confirmed Date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Message ESC 1')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Message ESC 2')}</Data></Cell>
    </Row>
    % for l in o.simu_line_ids:
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.in_product_id and obj_name_get('product.product', l.in_product_id.id) or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.in_nomen or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.in_comment or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.in_qty or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.in_uom and obj_name_get('product.uom', l.in_uom.id) or '')|x}</Data></Cell>
        % if isDate(l.in_drd):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${(l.in_drd)|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        % endif
        % if isDate(l.in_dcd):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${(l.in_dcd)|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ></Cell>
        % endif
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.in_price or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.in_currency and obj_name_get('res.currency', l.in_currency.id) or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.in_line_number)|x}</Data></Cell>
        % if l.type_change == 'del':
            <Cell ss:StyleID="line_change" ><Data ss:Type="String">${(getSel(l, 'chg_text') or '')|x}</Data></Cell>
        % else:
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(getSel(l, 'chg_text') or '')|x}</Data></Cell>
        % endif
        % if not l.type_change == 'ignore' and (l.type_change == 'del' or l.in_product_id != l.imp_product_id):
        <Cell ss:StyleID="line_change" ><Data ss:Type="String">${(l.imp_product_id and obj_name_get('product.product', l.imp_product_id.id) or '')|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.imp_product_id and obj_name_get('product.product', l.imp_product_id.id) or '')|x}</Data></Cell>
        % endif
        % if not l.type_change == 'ignore' and (l.type_change == 'del' or l.in_qty != l.imp_qty):
        <Cell ss:StyleID="line_change" ><Data ss:Type="Number">${(l.imp_qty or 0.00)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.imp_qty or 0.00)|x}</Data></Cell>
        % endif
        % if not l.type_change == 'ignore' and (l.type_change == 'del' or l.in_price != l.imp_price):
        <Cell ss:StyleID="line_change" ><Data ss:Type="Number">${(l.imp_price or 0.00)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.imp_price or 0.00)|x}</Data></Cell>
        % endif
        % if not l.type_change == 'ignore' and (l.type_change == 'del' or l.imp_discrepancy != 0.00):
        <Cell ss:StyleID="line_change" ><Data ss:Type="Number">${(l.imp_discrepancy or 0.00)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.imp_discrepancy or 0.00)|x}</Data></Cell>
        % endif
        % if not l.type_change == 'ignore' and (l.type_change == 'del' or l.in_currency != l.imp_currency):
        <Cell ss:StyleID="line_change" ><Data ss:Type="String">${(l.imp_currency and obj_name_get('res.currency', l.imp_currency.id) or '')|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.imp_currency and obj_name_get('res.currency', l.imp_currency.id) or '')|x}</Data></Cell>
        % endif
        % if not l.type_change == 'ignore' and (l.type_change == 'del' or l.in_drd != l.imp_drd) and isDate(l.imp_drd):
        <Cell ss:StyleID="line_change_short_date" ><Data ss:Type="DateTime">${(l.imp_drd)|n}T00:00:00.000</Data></Cell>
        % elif isDate(l.imp_drd):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${(l.imp_drd)|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ></Cell>
        % endif
        % if not l.type_change == 'ignore' and ((l.type_change == 'del' or l.in_dcd != l.imp_dcd) and isDate(l.imp_dcd)):
        <Cell ss:StyleID="line_change_short_date" ><Data ss:Type="DateTime">${(l.imp_dcd)|n}T00:00:00.000</Data></Cell>
        % elif isDate(l.imp_dcd):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${(l.imp_dcd)|n}T00:00:00.000</Data></Cell>
        % elif l.type_change == 'del':
        <Cell ss:StyleID="line_change"></Cell>
        % else:
        <Cell ss:StyleID="line" ></Cell>
        % endif
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.imp_esc1 or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.imp_esc2 or '')|x}</Data></Cell>
    </Row>
    % endfor

    <Row></Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Information (Line numbers refer to the line numbers of the PO confirmation import file)')}</Data></Cell>
        <Cell ss:StyleID="line" MergeAcross="3" ><Data ss:Type="String">${(o.message or '')|x}</Data></Cell>
    </Row>

</Table>
<x:WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
    <!--    <ProtectObjects>False</ProtectObjects>
    <ProtectScenarios>False</ProtectScenarios>
    <EnableSelection>UnlockedCells</EnableSelection>
    <AllowInsertRows />-->
</x:WorksheetOptions>
</ss:Worksheet>
% endfor
</Workbook>
