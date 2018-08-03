<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>${_('Analytic Allocation with Free - Report')}</Title>
</DocumentProperties>
<Styles>
<Style ss:ID="ssCell">
<Alignment ss:Vertical="Top" ss:WrapText="1"/>
</Style>
<Style ss:ID="ssCellBold">
<Font ss:Bold="1" />
<Alignment ss:Vertical="Top" ss:Horizontal="Left" ss:WrapText="1"/>
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
<Worksheet ss:Name="${_('Analytic Allocation with Free')}">
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120"/>
<Column ss:AutoFitWidth="1" ss:Width="90" ss:Span="10"/>

<!-- TABLE HEADER -->
<Row>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Entry Sequence')}</Data>
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
        <Data ss:Type="String">${_('Funding Pool')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Free 1')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Free 2')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Book. Amount')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Book. Currency')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Func. Amount')}</Data>
    </Cell>
    <Cell ss:StyleID="ssHeader">
        <Data ss:Type="String">${_('Func. Currency')}</Data>
    </Cell>
</Row>

<!-- LINES -->
% for line in lines(data):
<Row>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['entry_sequence']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['account']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['destination']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['cost_center']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['funding_pool']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['free1']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['free2']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${line['book_amount']}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['book_currency']|x}</Data>
    </Cell>
    <Cell ss:StyleID="ssNumber">
        <Data ss:Type="Number">${line['func_amount']}</Data>
    </Cell>
    <Cell ss:StyleID="ssBorder">
        <Data ss:Type="String">${line['func_currency']|x}</Data>
    </Cell>
</Row>
% endfor

</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <FitToPage/>
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14Analytic Allocation with Free - Report"/>
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
</Workbook>
