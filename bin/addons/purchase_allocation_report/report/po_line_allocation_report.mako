<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${_('PO lines allocation report')}</Title>
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
<Worksheet ss:Name="${_('PO lines allocation report')}">
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="65" ss:Span="18"/>

<!-- TABLE HEADER -->
<Row>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('PO')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Type')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Cat.')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('O. l.')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
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
    <Cell ss:StyleID="ssHeader">
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
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Requestor')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Partner Doc')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Comment')}</Data>
    </Cell>
</Row>

% for o in objects:
<Row>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ o.order_id.name or '' |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ getSel(o, 'order_type') or '' |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ getSel(o, 'order_category') or '' |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ o.line_number or '' |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ '[%s] %s' % (o.product_id.default_code or '', o.product_id.name or '') |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${ o.product_qty or 0.0 }</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ o.uom_id.name or '' |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${ o.unit_price or 0.0 }</Data>
    </Cell>
    <Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${ o.percentage or 0.0 }</Data>
    </Cell>
    <Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${ o.subtotal or 0.0 }</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ o.currency_id.name or '' |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ "%s %s" % (o.account_id.code, o.account_id.name) |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ o.destination_id.code or '' |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ o.cost_center_id.code or '' |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ o.source_doc or '' |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ o.requestor or '' |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ o.partner_doc or '' |x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${ o.comment or '' |x}</Data>
    </Cell>
</Row>

% endfor
</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <FitToPage/>
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14PO lines allocation report"/>
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
     <ActiveRow>18</ActiveRow>
    </Pane>
   </Panes>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
</WorksheetOptions>
</Worksheet>
</Workbook>
