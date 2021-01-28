<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>Unifield</Author>
  <LastAuthor>MSFUser</LastAuthor>
  <Created>2014-04-16T22:36:07Z</Created>
  <Company>Medecins Sans Frontieres</Company>
  <Version>11.9999</Version>
 </DocumentProperties>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>11640</WindowHeight>
  <WindowWidth>15480</WindowWidth>
  <WindowTopX>120</WindowTopX>
  <WindowTopY>75</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
 <Styles>
    <!-- ssCells -->
    <Style ss:ID="ssCell">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
    </Style>

    <!-- Line header -->
    <Style ss:ID="line_header">
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font x:Family="Swiss" ss:Bold="1"/>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="line_header_center">
        <Alignment ss:Horizontal="Center"/>
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font x:Family="Swiss" ss:Bold="1"/>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>

    <!-- Lines -->
    <Style ss:ID="line_left">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_left_no_digit">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
    </Style>
    <Style ss:ID="line_right">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
     <Style ss:ID="line_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_center_no_digit">
        <Alignment ss:Horizontal="Center" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
    </Style>
    <Style ss:ID="line_left_date">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="Short Date"/>
    </Style>
    <Style ss:ID="line_borders_top">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
    </Style>
    <Style ss:ID="line_borders_middle">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
    </Style>
    <Style ss:ID="line_borders_bottom">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
    </Style>

    <Style ss:ID="short_date">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
        <NumberFormat ss:Format="Short Date" />
    </Style>
    <Style ss:ID="short_date_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Bottom" ss:WrapText="1"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="Short Date"/>
    </Style>
 </Styles>

% for pt in objects:
<ss:Worksheet ss:Name="Pre-Packing Excel Report">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Item
        <Column ss:AutoFitWidth="1" ss:Width="40.0" />
        ## Code
        <Column ss:AutoFitWidth="1" ss:Width="110.0" />
        ## Description
        <Column ss:AutoFitWidth="1" ss:Width="250.0" />
        ## Comment
        <Column ss:AutoFitWidth="1" ss:Width="250.0" />
        ## Total Qty to pack
        <Column ss:AutoFitWidth="1" ss:Width="110.0" />
        ## Batch #
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## Expiry Date #
        <Column ss:AutoFitWidth="1" ss:Width="85.0" />
        ## CC
        <Column ss:AutoFitWidth="1" ss:Width="20.0" />
        ## DG
        <Column ss:AutoFitWidth="1" ss:Width="20.0" />
        ## CS
        <Column ss:AutoFitWidth="1" ss:Width="20.0" />
        ## Qty Packed
        <Column ss:AutoFitWidth="1" ss:Width="70.0"  />
        ## From pack
        <Column ss:AutoFitWidth="1" ss:Width="55.0"  />
        ## To pack
        <Column ss:AutoFitWidth="1" ss:Width="55.0"  />
        ## Weight per pack (kg)
        <Column ss:AutoFitWidth="1" ss:Width="105.0"  />
        ## Size (w x l x h) (cm)
        <Column ss:AutoFitWidth="1" ss:Width="125.0"  />
        ## Pack Type
        <Column ss:AutoFitWidth="1" ss:Width="80.0"  />

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="line_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Reference')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${pt.name|x}</Data></Cell>
            <Cell ss:StyleID="line_header" ss:MergeAcross="2"><Data ss:Type="String">${_('Shipper')|x}</Data></Cell>
            <Cell ss:StyleID="line_header" ss:MergeAcross="4"><Data ss:Type="String">${_('Consignee')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Date')|x}</Data></Cell>
            <Cell ss:StyleID="short_date_center"><Data ss:Type="DateTime">${time.strftime('%Y-%m-%d')|n}T00:00:00.000</Data></Cell>
            <Cell ss:StyleID="line_borders_top" ss:MergeAcross="2"><Data ss:Type="String">${getPickingShipper().get('shipper_name', '')|x}</Data></Cell>
            <Cell ss:StyleID="line_borders_top" ss:MergeAcross="4"><Data ss:Type="String">${getConsignee(pt)[0].get('consignee_name', '')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Requester Ref')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${pt.sale_id and pt.sale_id.client_order_ref or ''|x}</Data></Cell>
            <Cell ss:StyleID="line_borders_middle" ss:MergeAcross="2"><Data ss:Type="String">${getPickingShipper().get('shipper_contact', '')|x}</Data></Cell>
            <Cell ss:StyleID="line_borders_middle" ss:MergeAcross="4"><Data ss:Type="String">${getConsignee(pt)[0].get('consignee_contact', '')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Our Ref')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${pt.sale_id and pt.sale_id.name or ''|x}</Data></Cell>
            <Cell ss:StyleID="line_borders_middle" ss:MergeAcross="2"><Data ss:Type="String">${getPickingShipper().get('shipper_addr_street', '')|x}</Data></Cell>
            <Cell ss:StyleID="line_borders_middle" ss:MergeAcross="4"><Data ss:Type="String">${getConsignee(pt)[0].get('consignee_addr_street', '')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header" ss:MergeAcross="1"><Data ss:Type="String">${_('FO Date')|x}</Data></Cell>
            % if pt.sale_id:
            <Cell ss:StyleID="short_date_center"><Data ss:Type="DateTime">${pt.sale_id.date_order|n}T00:00:00.000</Data></Cell>
            % else:
            <Cell ss:StyleID="short_date_center"><Data ss:Type="String"></Data></Cell>
            % endif
            <Cell ss:StyleID="line_borders_middle" ss:MergeAcross="2"><Data ss:Type="String">${getPickingShipper().get('shipper_addr_zip_city', '')|x}</Data></Cell>
            <Cell ss:StyleID="line_borders_middle" ss:MergeAcross="4"><Data ss:Type="String">${getConsignee(pt)[0].get('consignee_addr_zip_city', '')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Packing Date')|x}</Data></Cell>
            % if pt.sale_id:
            <Cell ss:StyleID="short_date_center"><Data ss:Type="DateTime">${pt.sale_id.delivery_requested_date|n}T00:00:00.000</Data></Cell>
            % else:
            <Cell ss:StyleID="short_date_center"><Data ss:Type="String"></Data></Cell>
            % endif
            <Cell ss:StyleID="line_borders_middle" ss:MergeAcross="2"><Data ss:Type="String">${getPickingShipper().get('shipper_phone', '')|x}</Data></Cell>
            <Cell ss:StyleID="line_borders_middle" ss:MergeAcross="4"><Data ss:Type="String">${getConsignee(pt)[0].get('consignee_phone', '')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header" ss:MergeAcross="1"><Data ss:Type="String">${_('RTS Date')|x}</Data></Cell>
            % if pt.sale_id:
            <Cell ss:StyleID="short_date_center"><Data ss:Type="DateTime">${pt.sale_id.ready_to_ship_date|n}T00:00:00.000</Data></Cell>
            % else:
            <Cell ss:StyleID="short_date_center"><Data ss:Type="String"></Data></Cell>
            % endif
            <Cell ss:StyleID="line_borders_middle" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="line_borders_middle" ss:MergeAcross="4"><Data ss:Type="String"></Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Transport Mode')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${pt.sale_id and pt.sale_id.transport_type and getSel(pt.sale_id, 'transport_type') or ''|x}</Data></Cell>
            <Cell ss:StyleID="line_borders_bottom" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="line_borders_bottom" ss:MergeAcross="4"><Data ss:Type="String"></Data></Cell>
        </Row>

        <Row></Row>

        <%
            headers_list = [
                _('Item'),
                _('Code'),
                _('Description'),
                _('Comment'),
                _('Total Qty to pack'),
                _('Batch #'),
                _('Expiry Date #'),
                _('CC'),
                _('DG'),
                _('CS'),
                _('Qty Packed'),
                _('From pack'),
                _('To pack'),
                _('Weight per pack (kg)'),
                _('Size (w x l x h) (cm)'),
                _('Pack Type'),
            ]
        %>

        <Row ss:Height="18.25">
        % for h in headers_list:
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        % for m in sorted(pt.move_lines, key=lambda move: move.line_number):
            % if m.state == 'assigned':
            <Row ss:Height="14.25">
                <Cell ss:StyleID="line_center_no_digit"><Data ss:Type="Number">${m.line_number|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${m.product_id and m.product_id.default_code or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${m.product_id and m.product_id.name or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${m.comment or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${m.product_qty or 0|x}</Data></Cell>
                % if m.prodlot_id:
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${m.prodlot_id.name or ''|x}</Data></Cell>
                <Cell ss:StyleID="short_date_center"><Data ss:Type="DateTime">${m.prodlot_id.life_date|n}T00:00:00.000</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                <Cell ss:StyleID="short_date_center"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${m.product_id.is_kc and 'X' or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${m.product_id.dg_txt or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${m.product_id.cs_txt or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number"></Data></Cell>
                <Cell ss:StyleID="line_left_no_digit"><Data ss:Type="Number">${m.from_pack or 0|x}</Data></Cell>
                <Cell ss:StyleID="line_left_no_digit"><Data ss:Type="Number">${m.to_pack or 0|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="Number">${m.weight or 0|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${m.pack_type and m.pack_type.name or ''|x}</Data></Cell>
            </Row>
            %endif
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
