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
    <Style ss:ID="sheader">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"/>
   <Interior ss:Color="#BFBFBF" ss:Pattern="Solid"/>
   <NumberFormat/>
   <Protection/>
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
  <Style ss:ID="s67">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"/>
   <Interior ss:Color="#FABF8F" ss:Pattern="Solid"/>
   <NumberFormat/>
   <Protection ss:Protected="0"/>
  </Style>
  <Style ss:ID="s64">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"/>
   <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
   <NumberFormat/>
   <Protection/>
  </Style>
  <Style ss:ID="s64p">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"/>
   <Interior ss:Color="#FFE699" ss:Pattern="Solid"/>
   <NumberFormat/>
   <Protection/>
  </Style>
</Styles>
## ==================================== we loop over the incoming_shipment "objects" == incoming_shipment  ====================================================
% for o in objects:
<ss:Worksheet ss:Name="${"%s"%(o.name.split('/')[-1] or 'Sheet1')|x}" ss:Protected="0">
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
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Freight')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Order Reference')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.name or '')|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Origin')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.origin or '')|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Supplier')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.partner_id and o.partner_id.name or '')|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Transport mode')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.purchase_id and getSel(o.purchase_id, 'transport_type') or '')|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Notes')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.note or ''|x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Message ESC header')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
    </Row>

   <Row>
    <Cell ss:StyleID="s64"/>
    <Cell ss:StyleID="s64"><Data ss:Type="String">${_('Qty of parcels*')}</Data></Cell>
    <Cell ss:StyleID="s64"><Data ss:Type="String">${_('From parcel*')}</Data></Cell>
    <Cell ss:StyleID="s64"><Data ss:Type="String">${_('To parcel*')}</Data></Cell>
    <Cell ss:StyleID="s64"><Data ss:Type="String">${_('Weight*')}</Data></Cell>
    <Cell ss:StyleID="s64"><Data ss:Type="String">${_('Volume')}</Data></Cell>
    <Cell ss:StyleID="s64"><Data ss:Type="String">${_('Height')}</Data></Cell>
    <Cell ss:StyleID="s64"><Data ss:Type="String">${_('Length')}</Data></Cell>
    <Cell ss:StyleID="s64"><Data ss:Type="String">${_('Width')}</Data></Cell>
    <Cell ss:StyleID="s64"><Data ss:Type="String">${_('Packing List')}</Data></Cell>
    <Cell ss:StyleID="s64"><Data ss:Type="String">${_('ESC Message 1')}</Data></Cell>
    <Cell ss:StyleID="s64"><Data ss:Type="String">${_('ESC Message 2')}</Data></Cell>
   </Row>
   <Row>
    <Cell ss:StyleID="s67"><Data ss:Type="String">#</Data></Cell>
    <Cell ss:StyleID="s67"><Data ss:Type="Number"></Data></Cell>
    <Cell ss:StyleID="s67"><Data ss:Type="Number"></Data></Cell>
    <Cell ss:StyleID="s67"><Data ss:Type="Number"></Data></Cell>
    <Cell ss:StyleID="s67"><Data ss:Type="Number"></Data></Cell>
    <Cell ss:StyleID="s67"><Data ss:Type="Number"></Data></Cell>
    <Cell ss:StyleID="s67"><Data ss:Type="Number"></Data></Cell>
    <Cell ss:StyleID="s67"><Data ss:Type="Number"></Data></Cell>
    <Cell ss:StyleID="s67"><Data ss:Type="Number"></Data></Cell>
    <Cell ss:StyleID="s67"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="s67"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="s67"><Data ss:Type="String"></Data></Cell>
   </Row>
   <Row>
    <Cell ss:StyleID="s64p"><Data ss:Type="String">${_('Parcel No.')}</Data></Cell>
    <Cell ss:StyleID="s64p"><Data ss:Type="String">${_('Parcel ID')}</Data></Cell>

   </Row>

    
    <Row>
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('Line number*')}</Data></Cell>    
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('Ext. Reference')}</Data></Cell>    
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('Product Code*')}</Data></Cell>
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('Product Description')}</Data></Cell>
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('Product Qty*')}</Data></Cell>
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('Product UoM')}</Data></Cell>
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('Price Unit')}</Data></Cell>
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('Currency')}</Data></Cell>
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('Batch')}</Data></Cell>
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('Expiry date')}</Data></Cell>
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('ESC Message 1')}</Data></Cell>
        <Cell ss:StyleID="sheader" ><Data ss:Type="String">${_('ESC Message 2')}</Data></Cell>
    </Row>
    % for line in o.move_lines:
        % if line.state != 'cancel':
        <Row>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.line_number or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.purchase_line_id and line.purchase_line_id.external_ref or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id and line.product_id.default_code or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id and line.product_id.name or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.product_qty or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_uom.name or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="Number">${((line.purchase_line_id and line.purchase_line_id.price_unit) or (line.product_id and line.product_id.standard_price) or 0.00)|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.picking_id and line.picking_id.purchase_id and line.picking_id.purchase_id.pricelist_id.currency_id.name or line.company_id.currency_id.name or '')|x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.prodlot_id and line.prodlot_id.name or '')|x}</Data></Cell>
            % if isDate(line.expired_date):
            <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.expired_date|n}T00:00:00.000</Data></Cell>
            % else:
            <Cell ss:StyleID="line" ></Cell>
            % endif
            <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        </Row>
        % endif
    % endfor
</Table>
<x:WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
    <ProtectObjects>False</ProtectObjects>
</x:WorksheetOptions>
</ss:Worksheet>
% endfor
</Workbook>
