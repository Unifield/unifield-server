<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Title>${_('Invoice Excel Export')}</Title>
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
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
    </Borders>
  </Style>
  <Style ss:ID="line">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
    </Borders>
  </Style>
  <Style ss:ID="line_number">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
    </Borders>
    <NumberFormat ss:Format="Standard"/>
  </Style>
  <Style ss:ID="line_date">
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
<ss:Worksheet ss:Name="${"%s%s" % (_('Sheet'), 1)|x}">

<Table x:FullColumns="1" x:FullRows="1">
  <Column ss:AutoFitWidth="1" ss:Width="80" ss:Span="1"/>
  <Column ss:AutoFitWidth="1" ss:Width="120"/>
  <Column ss:AutoFitWidth="1" ss:Index="4" ss:Width="300"/>
  <Column ss:AutoFitWidth="1" ss:Width="110"/>
  <Column ss:AutoFitWidth="1" ss:Width="80" ss:Span="1"/>
  <Column ss:AutoFitWidth="1" ss:Width="110"/>
  <Column ss:AutoFitWidth="1" ss:Width="140"/>
  <Column ss:AutoFitWidth="1" ss:Width="110" ss:Span="2"/>
  <Column ss:AutoFitWidth="1" ss:Index="13" ss:Width="150"/>
  <Column ss:AutoFitWidth="1" ss:Width="100" ss:Span="1"/>
  <Column ss:AutoFitWidth="1" ss:Index="16" ss:Width="210"/>
  <Column ss:AutoFitWidth="1" ss:Width="200"/>
  <Column ss:AutoFitWidth="1" ss:Width="210" ss:Span="1"/>
  <Column ss:AutoFitWidth="1" ss:Width="150" ss:Span="1"/>

  <Row>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Document number')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Line number')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Product')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Description')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Quantity')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('UOM')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Percentage')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Unit price')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Subtotal')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Account')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Cost center')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Destination')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Voucher number')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Voucher status')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Posting date')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Ship #')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Partner')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('FO number')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('PO number')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Counterpart invoice number')}</Data></Cell>
      <Cell ss:StyleID="header"><Data ss:Type="String">${_('Counterpart invoice status')}</Data></Cell>
  </Row>

  <% document_number = 0 %>
  % for o in objects:
      <% document_number += 1 %>

      % for inv_line in o.invoice_line:
          % for distrib_line in distribution_lines(inv_line):
            <Row>
                <Cell ss:StyleID="line"><Data ss:Type="String">${document_number|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.line_number or ''|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.product_id and inv_line.product_id.default_code or ''|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.name|x}</Data></Cell>
                <Cell ss:StyleID="line_number"><Data ss:Type="Number">${inv_line.quantity|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.uos_id and inv_line.uos_id.name or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_number"><Data ss:Type="Number">${distrib_line['percentage']|x}</Data></Cell>
                <Cell ss:StyleID="line_number"><Data ss:Type="Number">${inv_line.price_unit|x}</Data></Cell>
                <Cell ss:StyleID="line_number"><Data ss:Type="Number">${distrib_line['subtotal']|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.account_id and inv_line.account_id.code or ''|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${distrib_line['cost_center']|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${distrib_line['destination']|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.invoice_id.number or ''|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${getSel(inv_line.invoice_id, 'state')|x}</Data></Cell>
                <Cell ss:StyleID="line_date"><Data ss:Type="DateTime">${inv_line.invoice_id.date_invoice or False|n}T00:00:00.000</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${shipment_number(o)|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.invoice_id.partner_id.name|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${fo_number(o)|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${po_number(inv_line)|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.invoice_id.counterpart_inv_number or ''|x}</Data></Cell>
                <Cell ss:StyleID="line"><Data ss:Type="String">${getSel(inv_line.invoice_id, 'counterpart_inv_status') or ''|x}</Data></Cell>
            </Row>
          % endfor
      % endfor
  % endfor
</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <FitToPage/>
   <PageSetup>
       <Layout x:Orientation="Landscape"/>
       <Header x:Margin="0.4921259845"/>
       <Footer x:Margin="0.4921259845"/>
       <PageMargins x:Bottom="0.984251969" x:Left="0.78740157499999996" x:Right="0.78740157499999996" x:Top="0.984251969"/>
   </PageSetup>
   <Print>
       <ValidPrinterInfo/>
       <PaperSizeIndex>9</PaperSizeIndex>
       <HorizontalResolution>600</HorizontalResolution>
       <VerticalResolution>600</VerticalResolution>
   </Print>
   <Selected/>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
</WorksheetOptions>
</ss:Worksheet>
</Workbook>
