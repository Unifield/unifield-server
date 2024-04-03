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
    <Style ss:ID="ssCell">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Bold="1" />
    </Style>
    <Style ss:ID="ssCellBlue">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Color="#0000FF" />
    </Style>

    <!-- File header -->
    <Style ss:ID="big_header">
        <Font x:Family="Swiss" ss:Size="14" ss:Bold="1"/>
    </Style>
    <Style ss:ID="file_header">
        <Font ss:Size="9" />
        <Interior ss:Color="#C0C0C0" ss:Pattern="Solid"/>
    </Style>

    <!-- Line header -->
    <Style ss:ID="line_header">
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font x:Family="Swiss" ss:Size="7" ss:Bold="1"/>
        <Interior/>
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
        <Font ss:Size="8" ss:Color="#0000FF"/>
    </Style>
    <Style ss:ID="line_left_green">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#1A721A"/>
    </Style>
    <Style ss:ID="line_right">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
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
        <Font ss:Size="8" ss:Color="#0000FF"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_left_date">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <NumberFormat ss:Format="[ENG][$-409]d\-mmm\-yyyy;@" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
    </Style>
    <Style ss:ID="line_left_date_fr">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <NumberFormat ss:Format="Short Date" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
    </Style>
    <Style ss:ID="short_date">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
        <NumberFormat ss:Format="[ENG][$-409]d\-mmm\-yyyy;@" />
        <Font ss:Size="8" ss:Color="#0000FF" />
    </Style>
    <Style ss:ID="short_date_fr">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
        <NumberFormat ss:Format="Short Date" />
        <Font ss:Size="8" ss:Color="#0000FF" />
    </Style>

    <Style ss:ID="line_left_grey">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#747474"/>
    </Style>
    <Style ss:ID="line_right_grey">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#747474"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
     <Style ss:ID="line_center_grey">
        <Alignment ss:Horizontal="Center" ss:Vertical="Bottom"/>
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#747474"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_left_date_grey">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <NumberFormat ss:Format="[ENG][$-409]d\-mmm\-yyyy;@" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#747474"/>
    </Style>
    <Style ss:ID="line_left_date_grey_fr">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <NumberFormat ss:Format="Short Date" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#747474"/>
    </Style>
</Styles>


% for r in objects:
<ss:Worksheet ss:Name="${_('IR Follow Up')|x}">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Order ref
        <Column ss:AutoFitWidth="1" ss:Width="130.0" />
        ## Location Requestor
        <Column ss:AutoFitWidth="1" ss:Width="170.0" />
        ## Requestor
        <Column ss:AutoFitWidth="1" ss:Width="150.0" />
        ## Origin
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## PO ref
        <Column ss:AutoFitWidth="1" ss:Width="150.0" />
        ## PO Supplier
        <Column ss:AutoFitWidth="1" ss:Width="150.0" />
        ## Doc. Status
        <Column ss:AutoFitWidth="1" ss:Width="60.75" />
        ## Line Status
        <Column ss:AutoFitWidth="1" ss:Width="60.75" />
        ## IR Details
        <Column ss:AutoFitWidth="1" ss:Width="200.0" />
        ## Received
        <Column ss:AutoFitWidth="1" ss:Width="54.75" />
        ## Requested Delivery Date
        <Column ss:AutoFitWidth="1" ss:Width="54.75" />
        ## Order line
        <Column ss:AutoFitWidth="1" ss:Width="19.00" />
        ## Product code
        <Column ss:AutoFitWidth="1" ss:Width="107.25" />
        ## Product description
        <Column ss:AutoFitWidth="1" ss:Width="239.25"  />
        ## Product comment
        <Column ss:AutoFitWidth="1" ss:Width="239.25"  />
        ## Qty Ordered
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## UoM Ordered
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## Qty Delivered
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />
        ## UoM Delivered
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />
        ## Delivery Order
        <Column ss:AutoFitWidth="1" ss:Width="120.0"  />
        ## Qty to deliver
        <Column ss:AutoFitWidth="1" ss:Width="50.5" />
        ## EDD
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## CDD
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## RTS Date
        <Column ss:AutoFitWidth="1" ss:Width="50.0" />
        ## MML Status
        <Column ss:AutoFitWidth="1" ss:Width="20.00" />
        ## MSL Status
        <Column ss:AutoFitWidth="1" ss:Width="20.00" />

        <Row ss:Height="18">
            <Cell ss:StyleID="big_header"><Data ss:Type="String">${_('INTERNAL REQUEST FOLLOW-UP')|x}</Data><NamedCell ss:Name="Print_Area"/></Cell>
        </Row>

        <Row ss:Height="10"></Row>

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Instance information')|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="file_header" ss:MergeAcross="4"><Data ss:Type="String">${_('Request parameters')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Name:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${r.company_id.instance_id.instance or '-'|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Requesting Location:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue" ss:MergeAcross="2"><Data ss:Type="String">${r.location_id.id and r.location_id.name or '-'|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String">${_('Address:')|x}</Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${r.company_id.partner_id.name or '-'|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Date start:')|x}</Data></Cell>
            % if isDate(r.start_date):
                % if getLang() == 'fr_MF':
                <Cell ss:StyleID="short_date_fr" ss:MergeAcross="2"><Data ss:Type="DateTime">${r.start_date|n}T00:00:00.000</Data></Cell>
                % else:
                <Cell ss:StyleID="short_date" ss:MergeAcross="2"><Data ss:Type="DateTime">${r.start_date|n}T00:00:00.000</Data></Cell>
                % endif
            % else:
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${r.company_id.partner_id.address[0].street or ''|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Date end:')|x}</Data></Cell>
            % if isDate(r.end_date):
                % if getLang() == 'fr_MF':
                <Cell ss:StyleID="short_date_fr" ss:MergeAcross="2"><Data ss:Type="DateTime">${r.end_date|n}T00:00:00.000</Data></Cell>
                % else:
                <Cell ss:StyleID="short_date" ss:MergeAcross="2"><Data ss:Type="DateTime">${r.end_date|n}T00:00:00.000</Data></Cell>
                % endif
            % else:
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${r.company_id.partner_id.address[0].zip|x} ${r.company_id.partner_id.address[0].city|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String">${_('Date of the request:')|x}</Data></Cell>
            % if r.report_date and isDateTime(r.report_date):
                % if getLang() == 'fr_MF':
                <Cell ss:StyleID="short_date_fr" ss:MergeAcross="2"><Data ss:Type="DateTime">${r.report_date[0:10]|n}T${r.report_date[11:19]|n}.000</Data></Cell>
                % else:
                <Cell ss:StyleID="short_date" ss:MergeAcross="2"><Data ss:Type="DateTime">${r.report_date[0:10]|n}T${r.report_date[11:19]|n}.000</Data></Cell>
                % endif
            % else:
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCellBlue"><Data ss:Type="String">${r.company_id.partner_id.address[0].country_id and r.company_id.partner_id.address[0].country_id.name or ''|x}</Data></Cell>
            <Cell ss:StyleID="ssCell"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="1"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
        </Row>

        <Row></Row>

        <%
            headers_list = [
                _('Order ref'),
                _('Location Requestor'),
                _('Requestor'),
                _('Origin'),
                _('PO ref'),
                _('PO Supplier'),
                _('Doc. Status'),
                _('Line Status'),
                _('IR Details'),
                _('Received'),
                _('RDD'),
                _('Item'),
                _('Code'),
                _('Description'),
                _('Comment'),
                _('Qty ordered'),
                _('UoM ordered'),
                _('Qty delivered'),
                _('UoM delivered'),
                _('Delivery Order'),
                _('Qty to deliver'),
                _('EDD'),
                _('CDD'),
                _('RTS Date'),
                _('MML'),
                _('MSL'),
            ]
        %>

        <Row>
        % for h in headers_list:
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        % for o in getOrders(r):
            % for line in getLines(o, report=r):
            <Row ss:Height="11.25">
                %if line.get('state', '') in ['cancel', 'cancel_r']:
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${o.name|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${o.location_requestor_id.name|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${o.requestor or ''|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${o.origin or ''|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line.get('po_name', '')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line.get('po_supplier', '')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${getSel(o, 'state')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line.get('state_display', '-')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${o.details or ''|x}</Data></Cell>
                    % if o.date_order and isDate(o.date_order):
                        % if getLang() == 'fr_MF':
                        <Cell ss:StyleID="line_left_date_grey_fr"><Data ss:Type="DateTime">${o.date_order|n}T00:00:00.000</Data></Cell>
                        % else:
                        <Cell ss:StyleID="line_left_date_grey"><Data ss:Type="DateTime">${o.date_order|n}T00:00:00.000</Data></Cell>
                        % endif
                    % else:
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String"></Data></Cell>
                    % endif
                    % if o.delivery_requested_date and isDate(o.delivery_requested_date):
                        % if getLang() == 'fr_MF':
                        <Cell ss:StyleID="line_left_date_grey_fr"><Data ss:Type="DateTime">${o.delivery_requested_date|n}T00:00:00.000</Data></Cell>
                        % else:
                        <Cell ss:StyleID="line_left_date_grey"><Data ss:Type="DateTime">${o.delivery_requested_date|n}T00:00:00.000</Data></Cell>
                        % endif
                    % else:
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String"></Data></Cell>
                    % endif
                    <Cell ss:StyleID="line_center_grey"><Data ss:Type="String">${line.get('line_number', '-')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line.get('product_code', '-') or ''|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line.get('product_name', '-') or ''|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line.get('line_comment', '-')|x}</Data></Cell>
                    % if line.get('ordered_qty'):
                    <Cell ss:StyleID="line_right_grey"><Data ss:Type="Number">${line.get('ordered_qty')}</Data></Cell>
                    % else:
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">N/A</Data></Cell>
                    % endif
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line.get('uom_id', '-')|x}</Data></Cell>
                    % if line.get('delivered_qty') or not line.get('cancelled_move'):
                    <Cell ss:StyleID="line_right_grey"><Data ss:Type="Number">${line.get('delivered_qty', 0)}</Data></Cell>
                    % else:
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">N/A</Data></Cell>
                    % endif
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line.get('delivered_uom', '')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line.get('delivery_order', '')|x}</Data></Cell>
                    % if line.get('cancelled_move'):
                    <Cell ss:StyleID="line_right_grey"><Data ss:Type="Number">0.00</Data></Cell>
                    % else:
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">-</Data></Cell>
                    % endif
                    % if line.get('edd'):
                        % if isDate(line['edd']):
                            % if getLang() == 'fr_MF':
                            <Cell ss:StyleID="line_left_date_grey_fr"><Data ss:Type="DateTime">${line['edd']|n}T00:00:00.000</Data></Cell>
                            % else:
                            <Cell ss:StyleID="line_left_date_grey"><Data ss:Type="DateTime">${line['edd']|n}T00:00:00.000</Data></Cell>
                            % endif
                        % else:
                            <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line['edd']|x}</Data></Cell>
                        % endif
                    % else:
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String"></Data></Cell>
                    % endif
                    % if line.get('cdd'):
                        % if isDate(line['cdd']):
                            % if getLang() == 'fr_MF':
                            <Cell ss:StyleID="line_left_date_grey_fr"><Data ss:Type="DateTime">${line['cdd']|n}T00:00:00.000</Data></Cell>
                            % else:
                            <Cell ss:StyleID="line_left_date_grey"><Data ss:Type="DateTime">${line['cdd']|n}T00:00:00.000</Data></Cell>
                            % endif
                        % else:
                            <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line['cdd']|x}</Data></Cell>
                        % endif
                    % else:
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String"></Data></Cell>
                    % endif
                    % if line.get('rts') and isDate(line['rts']):
                        % if getLang() == 'fr_MF':
                        <Cell ss:StyleID="line_left_date_grey_fr"><Data ss:Type="DateTime">${line['rts']|n}T00:00:00.000</Data></Cell>
                        % else:
                        <Cell ss:StyleID="line_left_date_grey"><Data ss:Type="DateTime">${line['rts']|n}T00:00:00.000</Data></Cell>
                        % endif
                    % else:
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String"></Data></Cell>
                    % endif
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line.get('mml_status', '-')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left_grey"><Data ss:Type="String">${line.get('msl_status', '-')|x}</Data></Cell>
                % else:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.name|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.location_requestor_id.name|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.requestor or ''|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.origin or ''|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('po_name', '')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('po_supplier', '')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${getSel(o, 'state')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('state_display', '-')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.details or ''|x}</Data></Cell>
                    % if o.date_order and isDate(o.date_order):
                        % if getLang() == 'fr_MF':
                        <Cell ss:StyleID="line_left_date_fr"><Data ss:Type="DateTime">${o.date_order|n}T00:00:00.000</Data></Cell>
                        % else:
                        <Cell ss:StyleID="line_left_date"><Data ss:Type="DateTime">${o.date_order|n}T00:00:00.000</Data></Cell>
                        % endif
                    % else:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    % endif
                    % if o.delivery_requested_date and isDate(o.delivery_requested_date):
                        % if getLang() == 'fr_MF':
                        <Cell ss:StyleID="line_left_date_fr"><Data ss:Type="DateTime">${o.delivery_requested_date|n}T00:00:00.000</Data></Cell>
                        % else:
                        <Cell ss:StyleID="line_left_date"><Data ss:Type="DateTime">${o.delivery_requested_date|n}T00:00:00.000</Data></Cell>
                        % endif
                    % else:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    % endif
                    <Cell ss:StyleID="line_center"><Data ss:Type="String">${line.get('line_number', '-')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('product_code', '-') or ''|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('product_name', '-') or ''|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('line_comment', '-')|x}</Data></Cell>
                    % if line.get('ordered_qty'):
                    <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line.get('ordered_qty')}</Data></Cell>
                    % else:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">N/A</Data></Cell>
                    % endif
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('uom_id', '-')|x}</Data></Cell>
                    % if line.get('delivered_qty') or not line.get('cancelled_move'):
                    <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line.get('delivered_qty', 0)}</Data></Cell>
                    % else:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">N/A</Data></Cell>
                    % endif
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('delivered_uom', '')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${(line.get('delivery_order', '-') != '-' and line.get('delivery_order') or line.get('shipment', '-') != '-' and line.get('shipment')  or line.get('packing') or '-')|x}</Data></Cell>
                    % if not line.get('cancelled_move'):
                        % if line.get('extra_qty', False):
                        <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('backordered_qty', 0.00)} (+${line.get('extra_qty', 0.00)|x})</Data></Cell>
                        % else:
                        <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line.get('backordered_qty')}</Data></Cell>
                        % endif
                    % else:
                    <Cell ss:StyleID="line_right"><Data ss:Type="Number">0.00</Data></Cell>
                    % endif
                    % if line.get('edd'):
                        % if isDate(line['edd']):
                            % if getLang() == 'fr_MF':
                            <Cell ss:StyleID="line_left_date_fr"><Data ss:Type="DateTime">${line['edd']|n}T00:00:00.000</Data></Cell>
                            % else:
                            <Cell ss:StyleID="line_left_date"><Data ss:Type="DateTime">${line['edd']|n}T00:00:00.000</Data></Cell>
                            % endif
                        % else:
                            <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['edd']|x}</Data></Cell>
                        % endif
                    % else:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    % endif
                    % if line.get('cdd'):
                        % if isDate(line['cdd']):
                            % if getLang() == 'fr_MF':
                            <Cell ss:StyleID="line_left_date_fr"><Data ss:Type="DateTime">${line['cdd']|n}T00:00:00.000</Data></Cell>
                            % else:
                            <Cell ss:StyleID="line_left_date"><Data ss:Type="DateTime">${line['cdd']|n}T00:00:00.000</Data></Cell>
                            % endif
                        % else:
                            <Cell ss:StyleID="line_left"><Data ss:Type="String">${line['cdd']|x}</Data></Cell>
                        % endif
                    % else:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    % endif
                    % if line.get('rts') and isDate(line['rts']):
                        % if getLang() == 'fr_MF':
                        <Cell ss:StyleID="line_left_date_fr"><Data ss:Type="DateTime">${line['rts']|n}T00:00:00.000</Data></Cell>
                        % else:
                        <Cell ss:StyleID="line_left_date"><Data ss:Type="DateTime">${line['rts']|n}T00:00:00.000</Data></Cell>
                        % endif
                    % else:
                    <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                    % endif
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('mml_status', '-')|x}</Data></Cell>
                    <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('msl_status', '-')|x}</Data></Cell>
                % endif
            </Row>
            % endfor

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
