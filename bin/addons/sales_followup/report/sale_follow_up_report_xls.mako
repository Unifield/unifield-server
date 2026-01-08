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
    <Style ss:ID="ssCell">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
    </Style>
    <Style ss:ID="ssCellBold">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Bold="1" />
    </Style>
    <Style ss:ID="ssCellRightBold">
        <Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Bold="1" />
    </Style>
    <Style ss:ID="header">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Font ss:Bold="1" />
        <Interior ss:Color="#dddddd" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="headerLeft">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
        <Font ss:Bold="1" />
        <Interior ss:Color="#dddddd" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="headerRight">
        <Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
        <Font ss:Bold="1" />
        <Interior ss:Color="#dddddd" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="line">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="lineRight">
        <Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="lineInt">
    <Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
    <NumberFormat ss:Format="##0"/>
    </Style>
    <Style ss:ID="lineFloat">
    <Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
    <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="short_date">
     <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
     <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
     </Borders>
     <NumberFormat ss:Format="Short Date"/>
    </Style>
</Styles>

## COLUMNS
<%
col_count = 13
header_merge_accross_count = col_count - 2  ## merging cell self deduced
%>
% for o in objects:
% if o.order_id.procurement_request:
<ss:Worksheet ss:Name="${_('IR Follow Up')|x}">
% else:
<ss:Worksheet ss:Name="${_('FO Follow Up')|x}">
% endif
<Table x:FullColumns="1" x:FullRows="1">
## order line
<Column ss:AutoFitWidth="1" ss:Width="80" />
## product code
<Column ss:AutoFitWidth="1" ss:Width="70" />
## product description
<Column ss:AutoFitWidth="1" ss:Width="160" />
## proc. method
<Column ss:AutoFitWidth="1" ss:Width="80"  />
## po/cft
<Column ss:AutoFitWidth="1" ss:Width="50"  />
## ordered qty
<Column ss:AutoFitWidth="1" ss:Width="50"  />
## uom
<Column ss:AutoFitWidth="1" ss:Width="60"  />
## sourced  
<Column ss:AutoFitWidth="1" ss:Width="60"  />
## tender (status)
<Column ss:AutoFitWidth="1" ss:Width="120" />
## purchase order (status)
<Column ss:AutoFitWidth="1" ss:Width="120" />
## incoming shipment (status)
<Column ss:AutoFitWidth="1" ss:Width="120" />
## product available (status)
<Column ss:AutoFitWidth="1" ss:Width="120" />
## outgoing delivery (status)
<Column ss:AutoFitWidth="1" ss:Width="120" />

## WORKSHEET HEADER
<%
if header_merge_accross_count > 0:
    merge_accross = ' ss:MergeAcross="%d"' % (header_merge_accross_count, )
else:
    merge_accross = ''
%>
## internal reference
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Internal reference:')|x}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.order_id and o.order_id.name or ''|x}</Data></Cell>
</Row>
## customer referene
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Customer reference:')|x}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.cust_ref or ''|x}</Data></Cell>
</Row>
## creation date
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Creation date:')|x}</Data></Cell>
<% dt = parse_date_xls(o.creation_date) %>
% if dt:
    <Cell ss:StyleID="short_date"${merge_accross}><Data ss:Type="DateTime">${dt|n}</Data></Cell>
% else:
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String"></Data></Cell>
% endif
</Row>
## order state
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Order state:')|x}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.state or ''|x}</Data></Cell>
</Row>
## requested date
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Requested Delivery date:')|x}</Data></Cell>
<% dt = parse_date_xls(o.requested_date) %>
% if dt:
    <Cell ss:StyleID="short_date"${merge_accross}><Data ss:Type="DateTime">${dt|n}</Data></Cell>
% else:
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String"></Data></Cell>
% endif
</Row>
## confirmed date
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Confirmed Delivery date:')|x}</Data></Cell>
<% dt = parse_date_xls(o.confirmed_date) %>
% if dt:
    <Cell ss:StyleID="short_date"${merge_accross}><Data ss:Type="DateTime">${dt|n}</Data></Cell>
% else:
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String"></Data></Cell>
% endif
</Row>
<Row>
## separator line
% for c in range(0, col_count):
    <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
% endfor
</Row>

## TABLE DATA HEADER
<%
headers_list = [
    _('ORDER LINE'),
    _('PRODUCT CODE'),
    _('PRODUCT DESCRIPTION'),
    _('PROC. METHOD'),
    _('PO/CFT'),
    _('ORDERED QTY'),
    _('UOM'),
    _('SOURCED'),
    _('TENDER'),
    _('PURCHASE ORDER'),
    _('INCOMING SHIPMENT'),
    _('PRODUCT AVAILABLE'),
    _('OUTGOING DELIVERY'),
]
%>
<Row>
% for h in headers_list:
    <Cell ss:StyleID="header"><Data ss:Type="String">${h|x}</Data></Cell>
% endfor
</Row>

## TABLE DATA ROWS
% for line in o.line_ids:
<Row>
## 1) order line
    <Cell ss:StyleID="lineInt"><Data ss:Type="Number">${int(line.line_number)}</Data></Cell>
## 2) product code
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.product_id and line.product_id.default_code or ''|x}</Data></Cell>
## 3) product description
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.product_id and line.product_id.name or ''|x}</Data></Cell>
## 4) proc.method
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.procure_method and getSel(line, 'procure_method') or ''|x}</Data></Cell>
## 5) po/cft
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.po_cft and getSel(line, 'po_cft') or ''|x}</Data></Cell>
## 6) ordered qty
    <Cell ss:StyleID="lineFloat"><Data ss:Type="Number">${line.qty_ordered or 0.}</Data></Cell>
## 7) uom
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.uom_id and line.uom_id.name or ''|x}</Data></Cell>
## 8) sourced
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.sourced_ok or ''|x}</Data></Cell>
## 9) tender
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.tender_status or ''|x}</Data></Cell>
## 10) purchase order
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.purchase_status or ''|x}</Data></Cell>
## 11) incoming shipment
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.incoming_status or ''|x}</Data></Cell>
## 12) product available
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.product_available or ''|x}</Data></Cell>
## 13) outgoing delivery
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.outgoing_status or ''|x}</Data></Cell>
</Row>
% endfor

</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Footer x:Data="Page &amp;P of &amp;N"/>
   </PageSetup>
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
</ss:Worksheet>
% endfor
</Workbook>
