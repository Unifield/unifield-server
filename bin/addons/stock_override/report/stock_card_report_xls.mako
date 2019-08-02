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
    <Style ss:ID="MainTitle">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Font ss:Bold="1" ss:Size="12" />
        <Interior ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="header">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Font ss:Bold="1" />
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
   <NumberFormat ss:Format="Long Time"/>
  </Style>
  <Style ss:ID="header_date">
   <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
   <NumberFormat ss:Format="Short Date"/>
  </Style>
  <Style ss:ID="BoldHeader">
   <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
   <Font ss:Bold="1" />
  </Style>
  <Style ss:ID="balance">
   <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
   <Interior ss:Pattern="Solid"/>
	<Borders>
	  <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
	  <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
	</Borders>
  </Style>
</Styles>
## ================================= we loop over the stock_card_wizard "objects" == stock_card_wizard======================================
<%
def parse_origin(origin):
    if origin:
        return origin.replace(';', '; ').replace(':', ': ')  # force word wrap
    return ''
%>
% for o in objects:
<ss:Worksheet ss:Name="${"%s"%(o.location_id and o.location_id.name or 'Sheet1')|x}">
<Table ss:ExpandedColumCount="8" x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="0" ss:Width="73.00" />
<Column ss:AutoFitWidth="0" ss:Width="88.50" />
<Column ss:AutoFitWidth="0" ss:Width="150.00" />
<Column ss:AutoFitWidth="0" ss:Width="70.00" />
<Column ss:AutoFitWidth="0" ss:Width="82.00" />
<Column ss:Index="7" ss:AutoFitWidth="0" ss:Width="100.00" />
<Column ss:AutoFitWidth="0" ss:Width="104.00" />

    <Row AutoFitHeight="1">
        <Cell ss:StyleID="MainTitle" ss:MergeAcross="7" ><Data ss:Type="String">${_('STOCK CARD')|x}</Data></Cell>
    </Row>

    <Row >
        <Cell ss:MergeAcross="7" ><Data ss:Type="String"></Data></Cell>
    </Row>


    <Row AutoFitHeight="1">
        <Cell ss:StyleID="BoldHeader"><Data ss:Type="String">${_('From')|x}</Data></Cell>
        <Cell><Data ss:Type="String">${o.from_date or ''}</Data></Cell>
        <Cell ss:StyleID="BoldHeader"><Data ss:Type="String">${_('To')|x}</Data></Cell>
        <Cell><Data ss:Type="String">${o.to_date or ''}</Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
    </Row>
    <Row AutoFitHeight="1">
        <Cell ss:StyleID="BoldHeader"><Data ss:Type="String">${_('Location')|x}</Data></Cell>
        <Cell><Data ss:Type="String">${o.location_id and o.location_id.name or ''}</Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="BoldHeader"><Data ss:Type="String">${_('Stock Balance')|x}</Data></Cell>
        <Cell ss:StyleID="balance"><Data ss:Type="Number">${o.available_stock or 0.00}</Data></Cell>
        <Cell ss:StyleID="BoldHeader"><Data ss:Type="String">${_('UoM')|x}</Data></Cell>
        <Cell><Data ss:Type="String">${o.product_id and o.product_id.uom_id and o.product_id.uom_id.name or ''}</Data></Cell>
    </Row>
    <Row AutoFitHeight="1">
        <Cell ss:StyleID="BoldHeader"><Data ss:Type="String">${_('Code')|x}</Data></Cell>
        <Cell><Data ss:Type="String">${o.product_id and o.product_id.default_code or ''}</Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="BoldHeader"><Data ss:Type="String">${_('Batch Number')|x}</Data></Cell>
        <Cell><Data ss:Type="String">${o.prodlot_id and o.prodlot_id.name or ''}</Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
    </Row>
    <Row AutoFitHeight="1">
        <Cell ss:StyleID="BoldHeader"><Data ss:Type="String">${_('Description')|x}</Data></Cell>
        <Cell ss:MergeAcross="2"><Data ss:Type="String">${o.product_id.name}</Data></Cell>
        <Cell ss:StyleID="BoldHeader"><Data ss:Type="String">${_('Expiry Date')|x}</Data></Cell>
        <Cell><Data ss:Type="String">${o.prodlot_id and o.prodlot_id.life_date or ''}</Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
        <Cell><Data ss:Type="String"></Data></Cell>
    </Row>


    <Row>
        <Cell ss:MergeAcross="7" ><Data ss:Type="String"></Data></Cell>
    </Row>

    <Row AutoFitHeight="1">
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
    <Row AutoFitHeight="1">
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.date_done or ''|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.doc_ref or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${parse_origin(line.origin)|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.qty_in or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.qty_out or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.balance or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.src_dest or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.notes or '')|x}</Data></Cell>
    </Row>
    % endfor
</Table>
<x:WorksheetOptions/>
</ss:Worksheet>
% endfor
</Workbook>
