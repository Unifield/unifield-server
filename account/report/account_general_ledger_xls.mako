<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"
xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
xmlns:html="http://www.w3.org/TR/REC-html40">
<DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
<Title>General Ledger</Title>
</DocumentProperties>
<Styles>
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
</Styles>
<Worksheet ss:Name="Sheet">
<%
    max = 12
%>
<Table ss:ExpandedColumnCount="${max}" ss:ExpandedRowCount="1" x:FullColumns="1"
x:FullRows="1">
% for x in range(0,max):
<Column ss:AutoFitWidth="1" ss:Width="70" />
% endfor
<Row>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Chart of Account</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Fiscal Year</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Journals</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Display Account</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Filter By</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Entries Sorted By</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Target Moves</Data></Cell>
<Cell ss:StyleID="ssH"></Cell>
<Cell ss:StyleID="ssH"></Cell>
<Cell ss:StyleID="ssH"></Cell>
<Cell ss:StyleID="ssH"></Cell>
<Cell ss:StyleID="ssH"></Cell>
</Row>
<Row>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder"></Cell>
<Cell ss:StyleID="ssBorder"></Cell>
<Cell ss:StyleID="ssBorder"></Cell>
<Cell ss:StyleID="ssBorder"></Cell>
<Cell ss:StyleID="ssBorder"></Cell>
</Row>
<Row>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
<Cell ss:StyleID="">
</Cell>
</Row>

<Row>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Date</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Period</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">JRNL</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Partner</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Ref</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Move</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Entry Label</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Counterpart</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Debit</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Credit</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Balance</Data></Cell>
<Cell ss:StyleID="ssH"><Data ss:Type="String">Currency</Data></Cell>
</Row>
<Row>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
<Cell ss:StyleID="ssBorder">
    <Data ss:Type="String">TEST</Data>
</Cell>
</Row>

</Table>
<AutoFilter x:Range="R1C1:R1C18" xmlns="urn:schemas-microsoft-com:office:excel">
</AutoFilter>
</Worksheet>
</Workbook>
