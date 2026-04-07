SELECT

/* 

[NAME]

- HANA_ABAP_NumberRanges

[DESCRIPTION]

- Overview of ABAP number range details

[SOURCE]

- SAP Note 1969700

[DETAILS AND RESTRICTIONS]

- Table TNRO only available in SAP ABAP environments
- You have to be connected to the SAP<sid> schema otherwise the following error is issued:

  [259]: invalid table name: Could not find table/view TNRO in schema

- If access to ABAP objects is possible but you cannot log on as ABAP user, you can switch the default schema before executing the command:

  SET SCHEMA SAP<sid>

[VALID FOR]

- Revisions:              all
- Client application:     ABAP

[SQL COMMAND VERSION]

- 2024/05/01:  1.0 (initial version)

[INVOLVED TABLES]

- TNRO

[INPUT PARAMETERS]

- OBJECT

  Number range object

  'RF_BELEG'    --> Number range object RF_BELEG
  'BIM%'        --> Number range objects starting with "BIM"
  '%'           --> No restriction related to number range objects

- BUFFER_TYPE

  Number range buffer type

  'no'          --> Display number ranges without buffering
  'parallel'    --> Display number ranges with parallel buffering
  'main memory' --> Display number ranges with main memory buffering
  '%'           --> No restriction related to number range buffering

- NON_ROLLING

  Flag for non-rolling number ranges

  'X'           --> Display non-rolling number ranges
  ' '           --> Display rolling number ranges
  '%'           --> No restriction related to non-rolling flag

- TRANSACTION

  Maintenance transaction for number range

  'FBN1'        --> Mainteinance transaction FBN1
  '%'           --> No restriction related to maintenance transaction

[OUTPUT PARAMETERS]

- OBJECT:      Number range object
- BUFFER_TYPE: Number range buffer type
- BUFFER_SIZE: Number range buffer size (number of buffer entries)
- WARNING_PCT: Warning threshold in terms of remaining number range interval (%)
- NON_ROLLING: Non-rolling flag for number ranges

[EXAMPLE OUTPUT]

-----------------------------------------------------------------------
|OBJECT   |BUFFER_TYPE|BUFFER_SIZE|WARNING_PCT|NON_ROLLING|TRANSACTION|
-----------------------------------------------------------------------
|RE_BELEG |main memory|         10|        1.0|           |           |
|RFK_BELEG|no         |           |        1.0|           |           |
|RF_BELEG |main memory|         10|       10.0|           |FBN1       |
|RKE_BELEG|no         |           |        1.0|           |           |
|RK_BELEG |main memory|        100|        5.0|X          |KANK       |
|RV_BELEG |main memory|         10|        5.0|           |           |
-----------------------------------------------------------------------

*/

  N.OBJECT,
  MAP(N.BUFFER, '', 'no', 'S', 'parallel', 'X', 'main memory', 'L', 'local', 'P', 'local (WP ID)', N.BUFFER) BUFFER_TYPE,
  LPAD(LTRIM(N.NOIVBUFFER, '0'), 11) BUFFER_SIZE,
  LPAD(N.PERCENTAGE, 11) WARNING_PCT,
  N.NONRSWAP NON_ROLLING,
  N.CODE TRANSACTION
FROM
( SELECT               /* Modification section */
    '%' OBJECT,
    '%' BUFFER_TYPE,
    '%' NON_ROLLING,
    '%' TRANSACTION
  FROM
    DUMMY
) BI,
  TNRO N
WHERE
  N.OBJECT LIKE BI.OBJECT AND
  MAP(N.BUFFER, '', 'no', 'S', 'parallel', 'X', 'main memory', 'L', 'local', 'P', 'local (WP ID)', N.BUFFER) LIKE BI.BUFFER_TYPE AND
  N.NONRSWAP LIKE BI.NON_ROLLING AND
  N.CODE LIKE BI.TRANSACTION
ORDER BY
  N.OBJECT
  