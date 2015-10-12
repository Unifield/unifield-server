<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">

<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>Financing Contract List</Title>
</DocumentProperties>

<Styles>
<Style ss:ID="ssCell">
<Alignment ss:Vertical="Top" ss:WrapText="1"/>
</Style>
<Style ss:ID="ssH">
<Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
<Font ss:Bold="1" />
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
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
<Alignment ss:Vertical="Top" ss:WrapText="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssLineString">
<Alignment ss:Bottom="Top" ss:WrapText="1"/>
<Font ss:Size="8" ss:Italic="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssLineDate">
<Alignment ss:Bottom="Top" ss:WrapText="1"/>
<Font ss:Size="8" ss:Italic="1"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
</Style>
<Style ss:ID="ssLineNumber">
<Alignment ss:Horizontal="Right" ss:Vertical="Bottom" ss:WrapText="1"/>
<Font ss:Size="8"/>
<Borders>
  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
</Borders>
<NumberFormat ss:Format="#,##0.00"/>
</Style>
</Styles>

<Worksheet ss:Name="Sheet">

<%
default_col_width = 60
cols = [
    ('code', 'Financing contract code', {'width': 80, }, ),
    ( 'name', 'Financing contract name', {'width': 80, }, ),
    ('instance', 'Prop instance', {'width': 80, }, ),
    ('donor_code', 'Donor code', {'width': 120, }, ),
    ('donor_grant_reference', 'Donor grant reference', {'width': 120, }, ),
    ('hq_grant_reference', 'HQ grant reference', {'width': 120, }, ),
    ('eligibility_from_date', 'Start eligibility date', ),
    ('eligibility_to_date', 'End eligibility date', ),
    ('grant_amount', 'Grant amount', {'type': 'Number', }, ),
    ('reporting_currency', 'CCY', ),
    ('reporting_type', 'Reporting type', {'width': 80, }, ),
    ('state', 'State', ),
    ('cost_centers', 'Cost centers associated', {'width': 120, 'auto_width': True, }, ),
    ('earmarked_funding_pools', 'List of Funding pool associated for earmarked costs', {'width': 120,'auto_width': True, }, ),
    ('total_project_funding_pools', 'List of Funding pool associated for total project costs', {'width': 120,'auto_width': True, }, ),
]
%>
    
<Table x:FullColumns="1" x:FullRows="1">
% for c in cols:
<%
options = len(c) > 2 and c[2] or {}
auto_width = options.get('auto_width') and 'ss:AutoFitWidth="1"' or ''
width = str(options.get('width') or default_col_width)
%>
<Column ${auto_width} ss:Width="${width}" />
% endfor
<Row>
% for c in cols:
<Cell ss:StyleID="ssHeader"><Data ss:Type="String">${c[1]|x}</Data></Cell>
% endfor
</Row>

% for o in get_contract_list(objects):
<Row>
% for c in cols:
<%
options = len(c) > 2 and c[2] or {}
cell_type = options.get('type') or 'String'
%>
<Cell ss:StyleID="ssLine${cell_type}"><Data ss:Type="${cell_type}">${o.get(c[0]) or ''|x}</Data></Cell>
% endfor
</Row>
% endfor
</Table>

<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14General Ledger"/>
    <Footer x:Data="Page &amp;P of &amp;N"/>
   </PageSetup>
   <Print>
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
