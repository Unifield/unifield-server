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
    <Style ss:ID="big_header">
        <Font x:Family="Swiss" ss:Size="14" ss:Bold="1"/>
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    </Style>
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

% for o in objects:
<ss:Worksheet ss:Name="${_('Internal Request Export')|x}">
<Table x:FullColumns="1" x:FullRows="1">
    ## Line Number
    <Column ss:AutoFitWidth="1" ss:Width="120.75" />
    ## Product code
    <Column ss:AutoFitWidth="1" ss:Width="145.75" />
    ## Product description
    <Column ss:AutoFitWidth="1" ss:Width="250.25" />
    ## Qty
    <Column ss:AutoFitWidth="1" ss:Width="58.75" />
    ## Cost Price
    <Column ss:AutoFitWidth="1" ss:Width="75.75" />
    ## UoM
    <Column ss:AutoFitWidth="1" ss:Width="63.75" />
    ## Currency
    <Column ss:AutoFitWidth="1" ss:Width="63.75" />
    ## Comment
    <Column ss:AutoFitWidth="1" ss:Width="209.25" />
    ## Date of Stock Take
    <Column ss:AutoFitWidth="1" ss:Width="75.75" />

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Reference')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.name or '-' | x}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('To:')}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Date')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="DateTime">${o.date | n}T00:00:00.000</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('FO Ref.')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.origin or '-' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Origin Ref.')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${'' | x}</Data></Cell> <!-- TODO customer ref -->
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Incoming Ref.')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.incoming_id.name or '-' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Category')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.order_category or '-' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Packing Date')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="DateTime">${o.date_done | n}T00:00:00.000</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Total items')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${'-' | x}</Data></Cell> <!-- TODO -->
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Content')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${'-' | x}</Data></Cell> <!-- TODO -->
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Transport mode')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${'-' | x}</Data></Cell> <!-- TODO -->
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Priority')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${'-' | x}</Data></Cell> <!-- TODO -->
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('RTS Date')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="DateTime">${o.date_done | n}T00:00:00.000</Data></Cell> <!-- TODO -->
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Item')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Code')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Description')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Changed Article')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Comment')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Src. Location')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Qty in Stock')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Qty to Pick')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Qty Picked')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Batch')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Expiry Date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('KC')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('DG')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('CS')}</Data></Cell>
    </Row>
    % for move in o.move_lines:
      <Row>
          <Cell ss:StyleID="line" ><Data ss:Type="Number">${move.line_number or '' | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="String">${move.product_id.default_code or '' | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="String">${move.product_id.name or '' | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="String">${'' | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="String">${move.comment or '' | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="String">${move.location_id.name or '' | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="Number">${'' | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="Number">${'' | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="Number">${'' | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="String">${move.prodlot_id and move.prodlot_id.name or '' | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="DateTime">${move.expired_date or '' | n}T00:00:00.000</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="String">${move.kc_check and _('Yes') or _('No') | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="String">${move.dg_check and _('Yes') or _('No') | x}</Data></Cell>
          <Cell ss:StyleID="line" ><Data ss:Type="String">${move.np_check and _('Yes') or _('No') | x}</Data></Cell>
      </Row>
    % endfor
</Table>
<x:WorksheetOptions/>
<DataValidation xmlns="urn:schemas-microsoft-com:office:excel">
    <Range>R4C2:R4C2</Range>
    <Type>List</Type>
    <CellRangeList/>
    <Value>&quot;${_('Medical,Log,Service,Transport,Other')|x}&quot;</Value>
</DataValidation>
<DataValidation xmlns="urn:schemas-microsoft-com:office:excel">
    <Range>R5C2:R5C2</Range>
    <Type>List</Type>
    <CellRangeList/>
    <Value>&quot;${_('Normal,Emergency,Priority')|x}&quot;</Value>
</DataValidation>
</ss:Worksheet>
% endfor
</Workbook>
