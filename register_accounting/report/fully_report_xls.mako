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
  <Created>${time.strftime('%Y-%m-%dT%H:%M:%SZ')|n}</Created>
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
    <!-- Header title for EACH page/sheet @ the top -->
    <Style ss:ID="title">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:Indent="0"/>
      <Font ss:Bold="1"/>
    </Style>
    <!-- Labels for information in header part of each page/sheet -->
    <Style ss:ID="header_part">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="header_part_center">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="header_part_number">
      <Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <NumberFormat ss:Format="Standard"/>
    </Style>
    <Style ss:ID="column_headers">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Bold="1" ss:Size="11"/>
      <Interior ss:Color="#ffff66" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="analytic_header">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Font ss:Size="11"/>
      <Interior ss:Color="#ffff66" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="distribution_header">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center"/>
      <Font ss:Size="11"/>
      <Interior ss:Color="#b2b2b2" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="direct_invoice_header">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center"/>
      <Font ss:Size="11"/>
      <Interior ss:Color="#8cbb3c" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="left_bold">
      <Font ss:Bold="1"/>
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff"/>
    </Style>
    <Style ss:ID="centre">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <Font ss:Bold="1"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <!-- Only used for register lines account's code -->
    <Style ss:ID="number_centre_bold">
      <Font ss:Bold="1"/>
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <NumberFormat ss:Format="0"/>
    </Style>
    <Style ss:ID="number_centre">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <NumberFormat ss:Format="0"/>
    </Style>
    <Style ss:ID="ana_centre">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff" ss:Bold="1"/>
    </Style>
    <Style ss:ID="date">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <NumberFormat ss:Format="Short Date"/>
      <Font ss:Bold="1"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="amount_bold">
      <Alignment ss:Horizontal="Right" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Font ss:Bold="1"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <!-- Initially used for invoice line number -->
    <Style ss:ID="text_center">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <NumberFormat ss:Format="@"/>
    </Style>
    <!-- For Amount IN/OUT in register lines -->
    <Style ss:ID="amount">
      <Alignment ss:Horizontal="Right" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <!-- Formated Number (with thousand separator) for analytic distribution amounts (in blue font color) -->
    <Style ss:ID="ana_amount">
      <Alignment ss:Horizontal="Right" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff"/>
    </Style>
    <!-- Formated Number (without thousand separator) for analytic distribution amounts (in blue font color) -->
    <Style ss:ID="ana_percent">
      <Alignment ss:Horizontal="Right" ss:Indent="0"/>
      <NumberFormat ss:Format="Fixed"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff"/>
    </Style>
    <Style ss:ID="short_date2">
      <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
      <NumberFormat ss:Format="Short Date"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="invoice_header">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
  </Styles>
  <Worksheet ss:Name="Info">
    <Table>
      <Column ss:Width="105.1937"/>
      <Column ss:Width="64.0063"/>
      <Row ss:Height="12.1039">
        <Cell ss:MergeAcross="3" ss:StyleID="title">
          <Data ss:Type="String">REGISTER REPORT</Data>
        </Cell>
      </Row>
      <Row ss:Height="12.8126">
        <Cell ss:Index="2"/>
      </Row>
      <Row ss:Height="12.1039">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">Report Date:</Data>
        </Cell>
        <Cell ss:StyleID="short_date2" >
          <Data ss:Type="DateTime">${time.strftime('%Y-%m-%d')|n}T00:00:00.000</Data>
        </Cell>
      </Row>
      <Row ss:Height="12.6425">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">Prop. Instance</Data>
        </Cell>
        <Cell ss:StyleID="header_part_center">
          <Data ss:Type="String">${( company.instance_id and company.instance_id.code or '')|x}</Data>
        </Cell>
      </Row>
    </Table>
    <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
      <DoNotDisplayGridlines/>
    </WorksheetOptions>
  </Worksheet>
% for o in objects:
  <Worksheet ss:Name="${o.period_id.name|x}, ${o.journal_id.code|x}">
    <Table>
      <Column ss:Width="95.9527"/>
      <Column ss:Width="70" ss:Span="1"/>
      <Column ss:Width="155"/>
      <Column ss:Width="135"/>
      <Column ss:Width="170"/>
      <Column ss:Width="55"/>
      <Column ss:Width="65"/>
      <Column ss:Width="60"/>
      <Column ss:Width="66"/>
      <Column ss:Width="72" ss:Span="2"/>
      <Column ss:Width="36" ss:Span="1"/>
      <Row ss:Height="19.3039">
        <Cell ss:MergeAcross="3" ss:StyleID="title">
          <Data ss:Type="String">${o.journal_id.type == 'cash' and _('CASH REGISTER') or o.journal_id.type == 'bank' and _('BANK REGISTER') or o.journal_id.type == 'cheque' and _('CHEQUE REGISTER') or ''|x} REPORT</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">Name: </Data>
        </Cell>
        <Cell ss:StyleID="header_part_center">
          <Data ss:Type="String">${o.name or ''|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">Period: </Data>
        </Cell>
        <Cell ss:StyleID="header_part_center">
          <Data ss:Type="String">${o.period_id and o.period_id.name or ''|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">Currency: </Data>
        </Cell>
        <Cell ss:StyleID="header_part_center">
          <Data ss:Type="String">${o.currency and o.currency.name or ''|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">Starting balance: </Data>
        </Cell>
        <Cell ss:StyleID="header_part_number">
          <Data ss:Type="Number">${o.balance_start or 0.0|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">Closing balance: </Data>
        </Cell>
        <Cell ss:StyleID="header_part_number">
          <Data ss:Type="Number">${o.balance_end_real or 0.0|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">Calculated balance: </Data>
        </Cell>
        <Cell ss:StyleID="header_part_number">
          <Data ss:Type="Number">${o.balance_end or 0.0|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">State: </Data>
        </Cell>
        <Cell ss:StyleID="header_part_center">
          <Data ss:Type="String">${o.state and getSel(o, 'state') or ''|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
      </Row>
      <Row ss:AutoFitHeight="0" ss:Height="29.1118">
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Entry type</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Doc Date</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Post Date</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Sequence</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Desc</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Ref</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Acct</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Third Parties</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">IN</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">OUT</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Dest</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">CC</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">FP</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Rec?</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Status</Data>
        </Cell>
      </Row>
% for line in sorted(o.line_ids, key=lambda x: x.sequence_for_reference):
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="centre">
          <Data ss:Type="String">${line.direct_invoice and _('Direct Invoice') or line.from_cash_return and _('Cash Return') or line.is_down_payment and _('Down Payment') and line.from_import_cheque_id and _('Cheque Import') or (line.transfer_journal_id and not line.is_transfer_with_change and _('Transfer')) or (line.transfer_journal_id and line.is_transfer_with_change and _('Transfer with change')) or line.imported_invoice_line_ids and _('Imported Invoice') or line.from_import_cheque_id and _('Imported Cheque') or _('Direct Payment')|x}</Data>
        </Cell>
        <Cell ss:StyleID="date">
          <Data ss:Type="DateTime">${line.document_date|n}T00:00:00.000</Data>
        </Cell>
        <Cell ss:StyleID="date">
          <Data ss:Type="DateTime">${line.date|n}T00:00:00.000</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.sequence_for_reference or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="centre">
          <Data ss:Type="String">${line.ref or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="number_centre_bold">
          <Data ss:Type="Number">${line.account_id.code|x}</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${(line.partner_id and line.partner_id.name or line.transfer_journal_id and line.transfer_journal_id.name or line.employee_id and line.employee_id.name or '')|x}</Data>
        </Cell>
        <Cell ss:StyleID="amount_bold">
          <Data ss:Type="Number">${line.amount_in or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="amount_bold">
          <Data ss:Type="Number">${line.amount_out or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="centre">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="centre">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="centre">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="centre">
          <Data ss:Type="String">${line.reconciled and 'X' or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="centre">
          <Data ss:Type="String">${line.state and getSel(line, 'state') or ''|x}</Data>
        </Cell>
      </Row>

% if line.analytic_distribution_id and line.analytic_distribution_id.funding_pool_lines:
% for ana_line in line.analytic_distribution_id.funding_pool_lines:
      <Row>
        <Cell ss:Index="10" ss:StyleID="ana_amount">
          <Data ss:Type="Number">${line.amount and ana_line.percentage and (abs((line.amount or 0.0) * (ana_line.percentage or 0.0) / 100)) or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${ana_line.destination_id and ana_line.destination_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${ana_line.cost_center_id and ana_line.cost_center_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${ana_line.analytic_id and ana_line.analytic_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_percent">
          <Data ss:Type="Number">${ana_line.percentage or 0.0}</Data>
        </Cell>
      </Row>
% endfor
% endif

<!-- Direct invoice and invoice that comes from a PL (in a cash return) -->
% if line.invoice_id:
% for inv_line in line.invoice_id.invoice_line:
      <Row>
        <Cell ss:Index="4" ss:StyleID="text_center">
          <Data ss:Type="String">${inv_line.line_number or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${inv_line.product_id and inv_line.product_id.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${inv_line.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="number_centre">
          <Data ss:Type="Number">${inv_line.account_id and inv_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="amount">
          <Data ss:Type="Number">${inv_line.price_subtotal or 0.0}</Data>
        </Cell>
      </Row>
% if (inv_line.analytic_distribution_id and inv_line.analytic_distribution_id.funding_pool_lines) or (inv_line.invoice_id and inv_line.invoice_id.analytic_distribution_id and inv_line.invoice_id.analytic_distribution_id.funding_pool_lines):
% if inv_line.analytic_distribution_id:
% for inv_ana_line in inv_line.analytic_distribution_id.funding_pool_lines:
      <Row>
        <Cell ss:Index="10" ss:StyleID="ana_amount">
          <Data ss:Type="Number">${inv_line.price_subtotal and inv_ana_line.percentage and (abs((inv_line.price_subtotal or 0.0) * (inv_ana_line.percentage or 0.0) / 100)) or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.destination_id and inv_ana_line.destination_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.cost_center_id and inv_ana_line.cost_center_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.analytic_id and inv_ana_line.analytic_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_percent">
          <Data ss:Type="Number">${inv_ana_line.percentage or 0.0}</Data>
        </Cell>
      </Row>
% endfor
% elif inv_line.invoice_id.analytic_distribution_id:
% for inv_ana_line in inv_line.invoice_id.analytic_distribution_id.funding_pool_lines:
      <Row>
        <Cell ss:Index="10" ss:StyleID="ana_amount">
          <Data ss:Type="Number">${inv_line.price_subtotal and inv_ana_line.percentage and (abs((inv_line.price_subtotal or 0.0) * (inv_ana_line.percentage or 0.0) / 100)) or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.destination_id and inv_ana_line.destination_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.cost_center_id and inv_ana_line.cost_center_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.analytic_id and inv_ana_line.analytic_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_percent">
          <Data ss:Type="Number">${inv_ana_line.percentage or 0.0}</Data>
        </Cell>
      </Row>
% endfor
% endif
% endif
% endfor
% endif

<!-- Imported invoice (pending payments) -->
% if line.imported_invoice_line_ids:
% for ji in line.imported_invoice_line_ids:
% for imp_inv_line in ji.invoice.invoice_line:
      <Row>
        <Cell ss:Index="4" ss:StyleID="text_center">
          <Data ss:Type="String">${imp_inv_line.line_number or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${imp_inv_line.product_id and imp_inv_line.product_id.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${imp_inv_line.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="number_centre">
          <Data ss:Type="Number">${imp_inv_line.account_id and imp_inv_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="amount">
          <Data ss:Type="Number">${imp_inv_line.price_subtotal or 0.0}</Data>
        </Cell>
      </Row>
% if (imp_inv_line.analytic_distribution_id and imp_inv_line.analytic_distribution_id.funding_pool_lines) or (imp_inv_line.invoice_id and imp_inv_line.invoice_id.analytic_distribution_id and imp_inv_line.invoice_id.analytic_distribution_id.funding_pool_lines):
% if imp_inv_line.analytic_distribution_id:
% for inv_ana_line in imp_inv_line.analytic_distribution_id.funding_pool_lines:
      <Row>
        <Cell ss:Index="10" ss:StyleID="ana_amount">
          <Data ss:Type="Number">${imp_inv_line.price_subtotal and inv_ana_line.percentage and (abs((imp_inv_line.price_subtotal or 0.0) * (inv_ana_line.percentage or 0.0) / 100)) or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.destination_id and inv_ana_line.destination_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.cost_center_id and inv_ana_line.cost_center_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.analytic_id and inv_ana_line.analytic_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_percent">
          <Data ss:Type="Number">${inv_ana_line.percentage or 0.0}</Data>
        </Cell>
      </Row>
% endfor
% elif imp_inv_line.invoice_id.analytic_distribution_id:
% for inv_ana_line in imp_inv_line.invoice_id.analytic_distribution_id.funding_pool_lines:
      <Row>
        <Cell ss:Index="10" ss:StyleID="ana_amount">
          <Data ss:Type="Number">${imp_inv_line.price_subtotal and inv_ana_line.percentage and (abs((imp_inv_line.price_subtotal or 0.0) * (inv_ana_line.percentage or 0.0) / 100)) or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.destination_id and inv_ana_line.destination_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.cost_center_id and inv_ana_line.cost_center_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_left">
          <Data ss:Type="String">${inv_ana_line.analytic_id and inv_ana_line.analytic_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="ana_percent">
          <Data ss:Type="Number">${inv_ana_line.percentage or 0.0}</Data>
        </Cell>
      </Row>
% endfor
% endif
% endif
% endfor
% endfor
% endif


% endfor
    </Table>
    <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
      <PageSetup>
        <Layout x:Orientation="Landscape" x:CenterHorizontal="1" x:CenterVertical="0"/>
        <Header x:Margin="0"/>
        <Footer x:Margin="0"/>
        <PageMargins x:Bottom="0.40" x:Left="0.40" x:Right="0.40" x:Top="0.40"/>
      </PageSetup>
      <Print>
        <ValidPrinterInfo/>
        <PaperSizeIndex>9</PaperSizeIndex>
        <Scale>60</Scale>
      </Print>
      <ShowPageBreakZoom/>
      <PageBreakZoom>70</PageBreakZoom>
      <DoNotDisplayGridlines/>
    </WorksheetOptions>
  </Worksheet>
% endfor
</Workbook>
