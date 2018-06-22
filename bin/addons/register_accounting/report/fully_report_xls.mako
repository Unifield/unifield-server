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
      <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <NumberFormat ss:Format="Standard"/>
    </Style>
    <Style ss:ID="column_headers">
      <Alignment ss:Horizontal="Left" ss:Vertical="Center"/>
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
    <!-- Blue left string for analytic distribution lines -->
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
    <!-- Blue left string for analytic distribution lines -->
    <Style ss:ID="blue_ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff"/>
    </Style>
    <!-- Grey left string for analytic distribution lines -->
    <Style ss:ID="grey_ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#9E9E9E"/>
    </Style>
    <!-- Purple left string for analytic distribution lines -->
    <Style ss:ID="purple_ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#8b0082"/>
    </Style>
    <!-- Red left string for analytic distribution lines -->
    <Style ss:ID="red_ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#ff0000"/>
    </Style>
    <!-- Green left string for analytic distribution lines -->
    <Style ss:ID="green_ana_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#006400"/>
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
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
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
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
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
    <Style ss:ID="text_left">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
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
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
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
    <!-- Formated Number (with thousand separator) for analytic distribution amounts (in blue font color) -->
    <Style ss:ID="blue_ana_amount">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#0000ff"/>
    </Style>
    <!-- Formated Number (with thousand separator) for analytic distribution amounts (in grey font color) -->
    <Style ss:ID="grey_ana_amount">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#9E9E9E"/>
    </Style>
    <!-- Formated Number (with thousand separator) for analytic distribution amounts (in purple font color) -->
    <Style ss:ID="purple_ana_amount">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#8b0082"/>
    </Style>
    <!-- Formated Number in red for analytic distribution amounts -->
    <Style ss:ID="red_ana_amount">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#ff0000"/>
    </Style>
    <!-- Formated Number in green for analytic distribution amounts -->
    <Style ss:ID="green_ana_amount">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
      <Font ss:Color="#006400"/>
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
    <!-- Grey color for deleted entries, manual entries, DP Reversals, Payable Entries... -->
    <Style ss:ID="grey_left_bold">
      <Font ss:Bold="1" ss:Color="#9E9E9E"/>
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="grey_left">
      <Font ss:Color="#9E9E9E"/>
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="grey_centre">
      <Alignment ss:Horizontal="Center" ss:Indent="0"/>
      <Font ss:Bold="1" ss:Color="#9E9E9E"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="grey_amount_bold">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Standard"/>
      <Font ss:Bold="1" ss:Color="#9E9E9E"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
        <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="0.5" ss:Color="#000000"/>
      </Borders>
    </Style>
    <Style ss:ID="grey_date">
      <Alignment ss:Horizontal="Left" ss:Indent="0"/>
      <NumberFormat ss:Format="Short Date"/>
      <Font ss:Bold="1" ss:Color="#9E9E9E"/>
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
      <Column ss:Width="101.1937"/>
      <Column ss:Width="63.01"/>
      <Row ss:Height="12.1039">
        <Cell ss:MergeAcross="3" ss:StyleID="title">
          <Data ss:Type="String">REGISTER REPORT</Data>
        </Cell>
      </Row>
      <Row ss:Height="12.81">
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
    <Names>
      <NamedRange ss:Name="Print_Titles" ss:RefersTo="=!R11"/>
    </Names>
    <Table>
      <Column ss:Width="93.75"/>
      <Column ss:Width="60.75" ss:Span="1"/>
      <Column ss:Width="132.75"/>
      <Column ss:Width="213.75"/>
      <Column ss:Width="98.25"/>
      <Column ss:Width="150.75"/>
      % if o.journal_id.type == 'cheque':
        <Column ss:Width="65"/>
      % endif
      <Column ss:Width="92.25"/>
      <Column ss:Width="134.25"/>
      <Column ss:Width="60"/>
      <Column ss:Width="66"/>
      <Column ss:Width="30.75"/>
      <Column ss:Width="72" ss:Span="3"/>
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
          <Data ss:Type="String">${_('Code:')}</Data>
        </Cell>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${o.journal_id.code|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">Period: </Data>
        </Cell>
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">${o.period_id and o.period_id.name or ''|x}</Data>
        </Cell>
      </Row>
      <Row ss:Height="14.5134">
        <Cell ss:StyleID="header_part">
          <Data ss:Type="String">Currency: </Data>
        </Cell>
        <Cell ss:StyleID="header_part">
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
        <Cell ss:StyleID="header_part">
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
          <Data ss:Type="String">Free Ref</Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="column_headers">
            <Data ss:Type="String">Chk num</Data>
          </Cell>
        % endif
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
          <Data ss:Type="String">Free 1</Data>
        </Cell>
        <Cell ss:StyleID="column_headers">
          <Data ss:Type="String">Free 2</Data>
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
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.direct_invoice and _('Direct Invoice') or (line.from_cash_return and line.account_id.type_for_register == 'advance' and _('Advance Return')) or line.is_down_payment and _('Down Payment') and line.from_import_cheque_id and _('Cheque Import') or (line.transfer_journal_id and not line.is_transfer_with_change and _('Transfer')) or (line.transfer_journal_id and line.is_transfer_with_change and _('Transfer with change')) or line.imported_invoice_line_ids and _('Imported Invoice') or line.from_import_cheque_id and _('Imported Cheque') or _('Direct Payment')|x}</Data>
        </Cell>
        % if isDate(line.document_date):
        <Cell ss:StyleID="date">
          <Data ss:Type="DateTime">${line.document_date|n}T00:00:00.000</Data>
        </Cell>
        % else:
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % endif
        % if isDate(line.date):
        <Cell ss:StyleID="date">
          <Data ss:Type="DateTime">${line.date|n}T00:00:00.000</Data>
        </Cell>
        % else:
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % endif
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.sequence_for_reference or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${getRegRef(line) or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="left_bold">
            <Data ss:Type="String">${line.cheque_number}</Data>
          </Cell>
        % endif
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.account_id.code + ' ' + line.account_id.name|x}</Data>
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
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.reconciled and 'X' or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left_bold">
          <Data ss:Type="String">${line.state and getSel(line, 'state') or ''|x}</Data>
        </Cell>
      </Row>

<!-- if it is a Down Payment that has been partially or totally reversed -->
<% dp_reversals_ml = getDownPaymentReversals(line) %>
% for dp_reversal_ml in sorted(dp_reversals_ml, key=lambda x: x.move_id.name):
    <Row ss:Height="14.5134">
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('REV - Down Payment')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- SEQUENCE -->
          <Data ss:Type="String">${dp_reversal_ml.move_id.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- DESC -->
          <Data ss:Type="String">${dp_reversal_ml.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- REF -->
          <Data ss:Type="String">${dp_reversal_ml.ref or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
    </Row>
% endfor

<!-- if there are Trade Payable Entries (automatically generated) -->
<% partner_move_ids = line.partner_move_ids or False %>
% if partner_move_ids:
% for partner_move_id in sorted(partner_move_ids, key=lambda x: x.name):
    <Row ss:Height="14.5134">
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('Payable Entry')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- SEQUENCE -->
          <Data ss:Type="String">${partner_move_id.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- DESC -->
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- REF -->
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
    </Row>
% endfor
% endif

<!-- Direct invoice and invoice that comes from a PL (in a cash return) -->
<% move_lines = [] %>
<% invoice_move = line.invoice_id and line.invoice_id.move_id or line.advance_invoice_move_id %>
% if invoice_move:
<% move_lines = getMoveLines([invoice_move], line) %>
% elif line.imported_invoice_line_ids:
<% move_lines = getImportedMoveLines([ml for ml in line.imported_invoice_line_ids], line) %>
% elif line.direct_invoice_move_id:
<% move_lines = getMoveLines([line.direct_invoice_move_id], line) %>
% endif

% for inv_line in move_lines:
      <Row>
        <Cell ss:Index="4" ss:StyleID="text_left">
          <Data ss:Type="String">${hasattr(inv_line, 'line_number') and inv_line.line_number or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${inv_line.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${inv_line.move_id and inv_line.move_id.name or hasattr(inv_line, 'reference') and inv_line.reference or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${getFreeRef(inv_line) or ''|x}</Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
        <Cell ss:StyleID="left">
          <Data ss:Type="String"></Data>
        </Cell>
        % endif
        <Cell ss:StyleID="left">
          <Data ss:Type="String">${inv_line.account_id and inv_line.account_id.code + ' ' + inv_line.account_id.name or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="amount">
          <Data ss:Type="Number">${hasattr(inv_line, 'amount_currency') and inv_line.amount_currency or 0.0}</Data>
        </Cell>
      </Row>
% if hasattr(inv_line, 'analytic_lines'):
% for ana_line in sorted(getAnalyticLines([x.id for x in inv_line.analytic_lines]), key=lambda x: x.id):
<%
line_color = 'blue'
if ana_line.is_reallocated:
    line_color = 'purple'
elif ana_line.is_reversal:
    line_color = 'green'
elif ana_line.last_corrected_id:
    line_color = 'red'
endif
%>
      <Row>
        % if o.journal_id.type == 'cheque':
          <Cell ss:Index="9" ss:StyleID="${line_color}_ana_left">
        % else:
          <Cell ss:Index="8" ss:StyleID="${line_color}_ana_left">
        % endif
          <Data ss:Type="String">${ana_line.general_account_id.code + ' ' + ana_line.general_account_id.name|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_amount">
          <Data ss:Type="Number">${ana_line.amount_currency}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.destination_id and ana_line.destination_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.cost_center_id and ana_line.cost_center_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${not ana_line.free_account and ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.distrib_line_id and ana_line.distrib_line_id._name == 'free.1.distribution.line' and \
                                   ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.distrib_line_id and ana_line.distrib_line_id._name == 'free.2.distribution.line' and \
                                   ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${(ana_line.is_reallocated and _('Corrected')) or (ana_line.is_reversal and _('Reversal')) or ''}</Data>
        </Cell>
      </Row>
% endfor
% endif
% endfor

<!-- Display analytic lines linked to this register line -->
<%
a_lines = False
adv_return_aal = line.cash_return_move_line_id and line.cash_return_move_line_id.analytic_lines or []
adv_return_fp_lines = []
adv_return_free_lines = []
for adv_return_l in adv_return_aal:
    if adv_return_l.free_account:
        adv_return_free_lines.append(adv_return_l)
    else:
        adv_return_fp_lines.append(adv_return_l)
if line.fp_analytic_lines and not line.invoice_id and not line.imported_invoice_line_ids:
    a_lines = adv_return_fp_lines or line.fp_analytic_lines
%>
% if a_lines:
% for ana_line in sorted(a_lines, key=lambda x: x.id):
<%
line_color = 'blue'
if ana_line.is_reallocated:
    line_color = 'purple'
elif ana_line.is_reversal:
    line_color = 'green'
elif ana_line.last_corrected_id:
    line_color = 'red'
endif
%>
% if not ana_line.free_account:
      <Row>
        % if o.journal_id.type == 'cheque':
          <Cell ss:Index="9" ss:StyleID="${line_color}_ana_left">
        % else:
          <Cell ss:Index="8" ss:StyleID="${line_color}_ana_left">
        % endif
          <Data ss:Type="String">${ana_line.general_account_id.code + ' ' + ana_line.general_account_id.name|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_amount">
          <Data ss:Type="Number">${ana_line.amount_currency}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.destination_id and ana_line.destination_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.cost_center_id and ana_line.cost_center_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${(ana_line.is_reallocated and _('Corrected')) or (ana_line.is_reversal and _('Reversal')) or ''}</Data>
        </Cell>
      </Row>
% endif
% endfor
% endif

<!-- Display analytic lines Free 1 and Free 2 linked to this register line -->
<%
a_lines = False
if line.free_analytic_lines and not line.invoice_id and not line.imported_invoice_line_ids:
    a_lines = adv_return_free_lines or line.free_analytic_lines
%>
% if a_lines:
% for ana_line in sorted(a_lines, key=lambda x: x.id):
<%
line_color = 'blue'
if ana_line.is_reallocated:
    line_color = 'purple'
elif ana_line.is_reversal:
    line_color = 'green'
elif ana_line.last_corrected_id:
    line_color = 'red'
endif
%>
      <Row>
        % if o.journal_id.type == 'cheque':
          <Cell ss:Index="9" ss:StyleID="${line_color}_ana_left">
        % else:
          <Cell ss:Index="8" ss:StyleID="${line_color}_ana_left">
        % endif
          <Data ss:Type="String">${ana_line.general_account_id.code + ' ' + ana_line.general_account_id.name|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_amount">
          <Data ss:Type="Number">${ana_line.amount_currency}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.distrib_line_id and ana_line.distrib_line_id._name == 'free.1.distribution.line' and \
                                   ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${ana_line.distrib_line_id and ana_line.distrib_line_id._name == 'free.2.distribution.line' and \
                                   ana_line.account_id and ana_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${line_color}_ana_left">
          <Data ss:Type="String">${(ana_line.is_reallocated and _('Corrected')) or (ana_line.is_reversal and _('Reversal')) or ''}</Data>
        </Cell>
      </Row>
% endfor
% endif

% endfor

<!-- MANUAL ENTRIES -->
<% manual_amls = getManualAmls(o) %>
% for aml in sorted(manual_amls, key=lambda x: x.move_id.name):
    <Row ss:Height="14.5134">
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('Manual Journal Entry')|x}</Data>
        </Cell>
        % if isDate(aml.document_date):
          <Cell ss:StyleID="grey_date">
            <Data ss:Type="DateTime">${aml.document_date|n}T00:00:00.000</Data>
          </Cell>
        % else:
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        % if isDate(aml.date):
          <Cell ss:StyleID="grey_date">
            <Data ss:Type="DateTime">${aml.date|n}T00:00:00.000</Data>
          </Cell>
        % else:
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        <Cell ss:StyleID="grey_left_bold">
          <!-- SEQUENCE -->
          <Data ss:Type="String">${aml.move_id.name|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${aml.name|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${aml.ref or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        <Cell ss:StyleID="grey_left">
          <Data ss:Type="String">${"%s %s" % (aml.account_id.code, aml.account_id.name)|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${aml.partner_txt or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">${aml.credit_currency or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">${aml.debit_currency or 0.0}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${aml.reconcile_id and 'X' or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${aml.move_id.state and getSel(aml.move_id, 'state') or ''|x}</Data>
        </Cell>
    </Row>

    <!-- ANALYTIC LINES linked to this manual Journal Item -->
    <%
    manual_aal_lines = getManualAjis(aml)
    %>
    % for manual_aal in sorted(manual_aal_lines, key=lambda x: x.id):
        <%
        aal_color = getManualAalColor(manual_aal)
        %>
        <Row>
          <%
          cell_index = o.journal_id.type == 'cheque' and 9 or 8
          %>
          <Cell ss:Index="${cell_index}" ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String">${"%s %s" % (manual_aal.general_account_id.code, manual_aal.general_account_id.name)|x}</Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String"></Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String"></Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_amount">
            <Data ss:Type="Number">${manual_aal.amount_currency}</Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String">${manual_aal.destination_id and manual_aal.destination_id.code or ''|x}</Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String">${manual_aal.cost_center_id and manual_aal.cost_center_id.code or ''|x}</Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String">${manual_aal.account_id and manual_aal.account_id.code or ''|x}</Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String"></Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String"></Data>
          </Cell>
          <Cell ss:StyleID="${aal_color}_ana_left">
            <Data ss:Type="String">${(manual_aal.is_reallocated and _('Corrected')) or (manual_aal.is_reversal and _('Reversal')) or ''|x}</Data>
          </Cell>
        </Row>
    % endfor

    <!-- FREE1/FREE2 LINES linked to this manual Journal Item -->
    <%
    manual_free_lines = getManualFreeLines(aml)
    %>
    % for free_line in sorted(manual_free_lines, key=lambda x: x.id):
      <%
      aal_color = getManualAalColor(free_line)
      %>
      <Row>
        <%
        cell_index = o.journal_id.type == 'cheque' and 9 or 8
        %>
        <Cell ss:Index="${cell_index}" ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String">${"%s %s" % (free_line.general_account_id.code, free_line.general_account_id.name)|x}</Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_amount">
          <Data ss:Type="Number">${free_line.amount_currency}</Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String">${free_line.distrib_line_id and free_line.distrib_line_id._name == 'free.1.distribution.line' and \
                                   free_line.account_id and free_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String">${free_line.distrib_line_id and free_line.distrib_line_id._name == 'free.2.distribution.line' and \
                                   free_line.account_id and free_line.account_id.code or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="${aal_color}_ana_left">
          <Data ss:Type="String">${(free_line.is_reallocated and _('Corrected')) or (free_line.is_reversal and _('Reversal')) or ''|x}</Data>
        </Cell>
      </Row>
    % endfor
% endfor

<!-- DELETED ENTRIES -->
% for deleted_line in sorted(o.deleted_line_ids, key=lambda x: x.sequence):
    <Row ss:Height="14.5134">
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('Deleted Entry')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <!-- SEQUENCE -->
          <Data ss:Type="String">${deleted_line.sequence or ''|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        % if o.journal_id.type == 'cheque':
          <Cell ss:StyleID="grey_left_bold">
            <Data ss:Type="String"></Data>
          </Cell>
        % endif
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_amount_bold">
          <Data ss:Type="Number">0.0</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String">${_('FALSE')|x}</Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
        <Cell ss:StyleID="grey_left_bold">
          <Data ss:Type="String"></Data>
        </Cell>
    </Row>
% endfor

    </Table>
    <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
      <PageSetup>
        <Layout x:Orientation="Landscape" x:CenterHorizontal="1" x:CenterVertical="0"/>
        <Header x:Margin="0"/>
        <Footer x:Margin="0"/>
        <PageMargins x:Bottom="0.40" x:Left="0.40" x:Right="0.40" x:Top="0.40"/>
      </PageSetup>
      <FitToPage/>
      <Print>
        <FitHeight>0</FitHeight>
        <ValidPrinterInfo/>
        <PaperSizeIndex>9</PaperSizeIndex>
        <Scale>60</Scale>
      </Print>
      <PageBreakZoom>70</PageBreakZoom>
      <DoNotDisplayGridlines/>
    </WorksheetOptions>
  </Worksheet>
% endfor
</Workbook>
