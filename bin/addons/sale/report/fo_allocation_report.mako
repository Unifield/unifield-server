<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${_('FO allocation report')}</Title>
</DocumentProperties>
<Styles>
<Style ss:ID="ssCell">
<Alignment ss:Vertical="Top" ss:WrapText="1"/>
</Style>
<Style ss:ID="ssCellBold">
<Font ss:Bold="1" />
<Alignment ss:Vertical="Top" ss:Horizontal="Left" ss:WrapText="1"/>
</Style>
<Style ss:ID="ssTitle">
<Font ss:Bold="1" />
<Alignment ss:Vertical="Center" ss:Horizontal="Center" ss:WrapText="1"/>
</Style>
<Style ss:ID="ssCellRight">
<Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
</Style>
<Style ss:ID="ssCellRightBold">
<Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
<Font ss:Bold="1" />
</Style>
<Style ss:ID="ssBorder">
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssBorderTopLeftRight">
<Font ss:Bold="1" />
<Alignment ss:Vertical="Center" ss:Horizontal="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssBorderBottomLeftRight">
<Alignment ss:Vertical="Center" ss:Horizontal="Left" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssBorderDate">
<Alignment ss:Vertical="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<NumberFormat ss:Format="Short Date" />
</Style>
<Style ss:ID="ssNumber">
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
<NumberFormat ss:Format="#,##0.00"/>
</Style>
<Style ss:ID="ssHeader">
<Alignment ss:Vertical="Top" ss:Horizontal="Center" ss:WrapText="1"/>
<Font ss:Bold="1" />
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssHeaderNumber">
<Font ss:Bold="1" />
<Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<NumberFormat ss:Format="#,##0.00"/>
</Style>
<Style ss:ID="ssHeaderRight">
<Font ss:Bold="1" />
<Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssHeaderCell">
<Alignment ss:Vertical="Top" ss:Horizontal="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssHeaderDateCell">
<Alignment ss:Vertical="Top" ss:Horizontal="Center" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<NumberFormat ss:Format="Short Date" />
</Style>
<Style ss:ID="ssHeaderNumberCell">
<Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<NumberFormat ss:Format="#,##0.00"/>
</Style>
<Style ss:ID="ssDateTimeLeft">
<Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
<NumberFormat ss:Format="General Date" />
</Style>
</Styles>
% for o in objects:
<Worksheet ss:Name="${o.name|x}">
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="70" ss:Span="13"/>

<!-- HEADER -->
<Row>
    <Cell ss:StyleID="ssTitle" ss:MergeAcross="13">
       <Data ss:Type="String">${_('FIELD ORDER LINES ALLOCATION REPORT')}</Data>
    </Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
</Row>
<Row>
 <Cell ss:StyleID="ssHeader" ss:MergeAcross="1"><Data ss:Type="String">${_('Field Order')}</Data></Cell>
 <Cell ss:StyleID="ssHeader" ss:MergeAcross="1"><Data ss:Type="String">${_('Customer')}</Data></Cell>
 <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Order Type')}</Data></Cell>
 <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Order Category')}</Data></Cell>
 <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Priority')}</Data></Cell>
 <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Creation Date')}</Data></Cell>
 <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('Creator')}</Data></Cell>
 <Cell ss:StyleID="ssHeader"><Data ss:Type="String">${_('State')}</Data></Cell>
 <Cell ss:StyleID="ssHeader" ss:MergeAcross="3"><Data ss:Type="String">${_('Details')}</Data></Cell>
</Row>
<Row>
     <Cell ss:StyleID="ssHeaderCell" ss:MergeAcross="1">
        <Data ss:Type="String">${ o.name or ''|x}</Data>
     </Cell>
     <Cell ss:StyleID="ssHeaderCell" ss:MergeAcross="1">
        <Data ss:Type="String">${ o.partner_id.name or ''|x}</Data>
     </Cell>
     <Cell ss:StyleID="ssHeaderCell">
        <Data ss:Type="String">${ getSel(o, 'order_type') or ''|x}</Data>
     </Cell>
    <Cell ss:StyleID="ssHeaderCell">
        <Data ss:Type="String">${ getSel(o, 'categ') or ''|x}</Data>
     </Cell>
     <Cell ss:StyleID="ssHeaderCell">
        <Data ss:Type="String">${ getSel(o, 'priority') or ''|x}</Data>
     </Cell>
    <Cell ss:StyleID="ssHeaderDateCell">
        <Data ss:Type="DateTime">${o.date_order|n}T00:00:00.000</Data>
     </Cell>
    <Cell ss:StyleID="ssHeaderCell">
        <Data ss:Type="String">${ o.user_id.name or ''|x}</Data>
     </Cell>
    <Cell ss:StyleID="ssHeaderCell">
        <Data ss:Type="String">${ getSel(o, 'state') or ''|x}</Data>
     </Cell>
    <Cell ss:StyleID="ssHeaderCell" ss:MergeAcross="3">
        <Data ss:Type="String">${ o.details or ''|x}</Data>
     </Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
</Row>

<!-- TABLE HEADER -->
<Row>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('O. l.')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader" ss:MergeAcross="1">
        <Data ss:Type="String">${_('Product')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Qty')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('UoM')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Unit Price')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">%</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Subtotal')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Currency')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader" ss:MergeAcross="1">
        <Data ss:Type="String">${_('Account')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Destination')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Cost Center')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Source Doc')}</Data>
    </Cell>
</Row>

% for line in o.order_line:
    % for dline in get_distrib_lines(line):
        <Row>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${ line.line_number or '' |x}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder" ss:MergeAcross="1">
                <Data ss:Type="String">${ line.product_id and '[%s] %s' % (line.product_id.default_code or '', line.product_id.name or '') or '' |x}</Data>
            </Cell>
            <Cell ss:StyleID="ssNumber">
                <Data ss:Type="Number">${ line.product_uom_qty or 0.0 }</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${ line.product_uom.name or '' |x}</Data>
            </Cell>
            <Cell ss:StyleID="ssNumber">
                <Data ss:Type="Number">${ line.price_unit or 0.0 }</Data>
            </Cell>
            <Cell ss:StyleID="ssNumber">
                <Data ss:Type="Number">${ dline and '%.2f' % dline.percentage or 0.0 }</Data>
            </Cell>
            <Cell ss:StyleID="ssNumber">
                <Data ss:Type="Number">${ dline and '%.2f' % (line.price_subtotal * dline.percentage / 100) or 0.0 }</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${ line.currency_id.name or ''|x}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder" ss:MergeAcross="1">
                <Data ss:Type="String">${ "%s %s" % (line.account_4_distribution.code or '', line.account_4_distribution.name or '') |x}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${ dline and dline.destination_id.code or '' |x}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${ dline and dline.analytic_id.code or '' |x}</Data>
            </Cell>
            <Cell ss:StyleID="ssBorder">
                <Data ss:Type="String">${ o.client_order_ref or '' |x}</Data>
            </Cell>
        </Row>
    % endfor
% endfor

<Row>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssHeader" ss:MergeAcross="1"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('TOTAL')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeaderNumber">
        <Data ss:Type="Number">${ get_total_amount(o) or 0.0 }</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssHeader" ss:MergeAcross="1"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String"></Data></Cell>
    <Cell ss:StyleID="ssHeader"><Data ss:Type="String"></Data></Cell>
</Row>

</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <FitToPage/>
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14FO allocation report"/>
    <Footer x:Data="Page &amp;P of &amp;N"/>
   </PageSetup>
   <Print>
    <FitHeight>0</FitHeight>
    <ValidPrinterInfo/>
    <PaperSizeIndex>9</PaperSizeIndex>
    <HorizontalResolution>600</HorizontalResolution>
    <VerticalResolution>600</VerticalResolution>
   </Print>
   <Selected/>
   <Panes>
    <Pane>
     <Number>3</Number>
     <ActiveRow>17</ActiveRow>
    </Pane>
   </Panes>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
</WorksheetOptions>
</Worksheet>
% endfor
</Workbook>
