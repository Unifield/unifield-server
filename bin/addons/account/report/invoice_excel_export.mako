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
<% sheet_suffix = 1 %>
% for o in objects:
<%
  if o.number:
      sheet_title = o.number
  else:
      sheet_title = "%s%s" % (_('Sheet'), sheet_suffix)
      sheet_suffix += 1  # each tab name must be different otherwise the file is "corrupted"
%>

<ss:Worksheet ss:Name="${sheet_title|x}">
<Table x:FullColumns="1" x:FullRows="1">
  <Column ss:AutoFitWidth="1" ss:Width="100" ss:Span="19"/>

  <Row>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Line number')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Description')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Quantity')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('UOM')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Percentage')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Subtotal')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Unit price')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Account')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Cost center')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Destination')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Voucher number')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Voucher status')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Posting date')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Ship #')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Partner')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('FO number')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('PO number')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Counterpart invoice number')}</Data></Cell>
      <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Counterpart invoice status')}</Data></Cell>
  </Row>
  % for inv_line in o.invoice_line:
      % for distrib_line in distribution_lines(inv_line):
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.line_number or ''|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.product_id and inv_line.product_id.default_code or ''|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.name|x}</Data></Cell>
            <Cell ss:StyleID="line_number"><Data ss:Type="Number">${inv_line.quantity|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.uos_id and inv_line.uos_id.name or ''|x}</Data></Cell>
            <Cell ss:StyleID="line_number"><Data ss:Type="Number">${distrib_line['percentage']|x}</Data></Cell>
            <Cell ss:StyleID="line_number"><Data ss:Type="Number">${distrib_line['subtotal']|x}</Data></Cell>
            <Cell ss:StyleID="line_number"><Data ss:Type="Number">${inv_line.price_unit|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.account_id.code|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${distrib_line['cost_center']|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${distrib_line['destination']|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.invoice_id.number or ''|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${getSel(inv_line.invoice_id, 'state')|x}</Data></Cell>
            <Cell ss:StyleID="line_date"><Data ss:Type="String">${inv_line.invoice_id.date_invoice or False|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${"TODO"|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.invoice_id.partner_id.name|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${"TODO"|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${"TODO"|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.invoice_id.counterpart_inv_number or ''|x}</Data></Cell>
            <Cell ss:StyleID="line"><Data ss:Type="String">${inv_line.invoice_id.counterpart_inv_status or ''|x}</Data></Cell>
        </Row>
      % endfor
  % endfor

</Table>
<x:WorksheetOptions/>
</ss:Worksheet>
% endfor
</Workbook>
