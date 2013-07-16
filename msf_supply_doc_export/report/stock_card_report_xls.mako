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
## ================================= we loop over the stock_card_wizard "objects" == stock_card_wizard======================================
% for o in objects:
<ss:Worksheet ss:Name="${"%s"%(o.location_id and o.location_id.name or 'Sheet1')|x}">
## definition of the columns' size
<% nb_of_columns = 8 %>
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="300" />
% for x in range(2,nb_of_columns - 1):
<Column ss:AutoFitWidth="1" ss:Width="60" />
% endfor
<Column ss:AutoFitWidth="1" ss:Width="250" />

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Doc. Reference')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Origin')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Qty IN')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Qty OUT')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Balance')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Source/Destination')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Notes')}</Data></Cell>
    </Row>
    % for line in o.card_lines:
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="DateTime">${(line.date_done or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.picking_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.origin or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.qty_in or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.qty_out or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.balance or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.location_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.notes or '')|x}</Data></Cell>
    </Row>
    % endfor
</Table>
<x:WorksheetOptions/>
</ss:Worksheet>
% endfor
</Workbook>
