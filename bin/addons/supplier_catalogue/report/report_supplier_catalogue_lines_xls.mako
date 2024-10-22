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
    </Style>
    <Style ss:ID="line">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
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
  </Style>
</Styles>
## ==================================== we loop over the supplier_catalogue "objects" == supplier.catalogue  ====================================================
% for o in getOrders(objects):
<ss:Worksheet ss:Name="${"%s"%(o.name.split('/')[-1] or 'Sheet1')|x}">
## definition of the columns' size
<% nb_of_columns = 8 %>
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="300" />
% for x in range(2,nb_of_columns - 1):
<Column ss:AutoFitWidth="1" ss:Width="60" />
% endfor
<Column ss:AutoFitWidth="1" ss:Width="250" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="60" />

## we loop over the purchase_order_line "%s"%po_name.split('/')[-1])
    
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Code')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Description')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Supplier Code')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('UoM')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Min. Qty')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Unit Price')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('SoQ Rounding')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Min. Order Qty.')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Comment')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Ranking')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('MML')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('MSL')}</Data></Cell>
    </Row>
    % for line in getLines(o):
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id.default_code or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_code or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.line_uom_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.min_qty or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.unit_price or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.rounding or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.min_order_qty or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.comment or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(line, 'ranking')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(line, 'mml_status')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(line, 'msl_status')|x}</Data></Cell>
    </Row>
    % endfor
</Table>
<x:WorksheetOptions/>
</ss:Worksheet>
% endfor
</Workbook>
