SELECT

/* 

[NAME]

- HANA_ABAP_TechnicalTableSettings

[DESCRIPTION]

- Overview of ABAP technical settings for tables

[SOURCE]

- SAP Note 1969700

[DETAILS AND RESTRICTIONS]

- Tables DD09L and DD02T only available in SAP ABAP environments
- You have to be connected to the SAP<sid> schema otherwise the following error is issued:

  [259]: invalid table name: Could not find table/view DD09L in schema

- If access to ABAP objects is possible but you cannot log on as ABAP user, you can switch the default schema before executing the command:

  SET SCHEMA SAP<sid>

- Older ABAP basis versions may not include all queried columns and terminations with "invalid column name" are possible, e.g.:

  [260]: invalid column name: D9L.LOAD_UNIT

- As a workaround, you can manually remove references to these columns from the SELECT.

[VALID FOR]

- Revisions:              all
- Client application:     ABAP

[SQL COMMAND VERSION]

- 2024/06/22:  1.0 (initial version)

[INVOLVED TABLES]

- DD02T
- DD09L

[INPUT PARAMETERS]

- TABLE_NAME           

  Table name or pattern

  'T000'          --> Specific table T000
  'T%'            --> All tables starting with 'T'
  '%'             --> All tables

- STORE

  SAP HANA table store

  'ROW'           --> Display tables that should be located in row store
  'COLUMN'        --> Display tables that should be located in column store
  '%'             --> No restriction related to store

- LOAD_UNIT

  Load unit of table on ABAP side (page -> NSE)

  'COLUMN_PREFERRED' --> Display tables with preferred column load unit
  'COLUMN_ENFORCED'  --> Display tables with enforced column load unit
  'PAGE_PREFERRED'   --> Display tables with preferred page load unit
  'PAGE_ENFORCED'    --> Display tables with enforced page load unit
  '%'                --> No restriction related to load unit

- TABLE_LOGGING

  Indicator for activated ABAP table logging (to table DBTABLOG)

  ' '             --> Display tables without activated table logging
  'X'             --> Display tables with activated table logging
  '%'             --> No restriction related to table logging

[OUTPUT PARAMETERS]

- TABLE_NAME:   Table name
- STORE:        Table store on SAP HANA side (ROW vs. COLUMN)
- LOAD_UNIT:    Table load unit 
- BUFFER:       ABAP table buffer state (SINGLE -> single record buffer, GENERIC -> generic key buffer, FULL -> full buffer)
- BUFF_ALLOWED: 'YES' if ABAP table buffering is allowed, otherwise 'NO'
- LOG:          'X' if ABAP table logging is active, otherwise ' '
- CHANGE_DATE:  Last change date (in terms of meta data / DDL)
- CHANGE_USER:  Last change user
- DESCRIPTION:  Table description

[EXAMPLE OUTPUT]

------------------------------------------------------------------------------------------------------------------------------------------------
|TABLE_NAME  |STORE |LOAD_UNIT       |BUFFER|BUFF_ALLOWED|LOG|CHANGE_DATE        |CHANGE_USER|DESCRIPTION                                      |
------------------------------------------------------------------------------------------------------------------------------------------------
|ARFCLOG     |COLUMN|COLUMN_PREFERRED|      |NO          |   |2015/06/01 00:00:00|SAP        |Description of tRFC States (Create, Send, Delete)|
|ARFCRCONTEXT|COLUMN|COLUMN_PREFERRED|      |NO          |   |2015/06/01 00:00:00|SAP        |Assignment of Context ID to TID                  |
|ARFCRDATA   |ROW   |COLUMN_PREFERRED|      |NO          |   |2013/05/31 00:00:00|SAP        |ARFC Call Data (Callers)                         |
|ARFCRSTATE  |ROW   |COLUMN_PREFERRED|      |NO          |   |2013/05/31 00:00:00|SAP        |Status of ARFC Calls on Receiver Side            |
|ARFCSDATA   |ROW   |COLUMN_PREFERRED|      |NO          |   |2013/05/31 00:00:00|SAP        |ARFC Call Data (Callers)                         |
|ARFCSSTATE  |ROW   |COLUMN_PREFERRED|      |NO          |   |2013/05/31 00:00:00|SAP        |Description of ARFC Call Status (Send)           |
------------------------------------------------------------------------------------------------------------------------------------------------

*/

  D9L.TABNAME TABLE_NAME,
  MAP(D9L.ROWORCOLST, 'R', 'ROW', 'C', 'COLUMN', 'UNDEFINED') STORE,
  MAP(D9L.LOAD_UNIT, '', 'COLUMN_PREFERRED', 'P', 'PAGE_PREFERRED', 'A', 'COLUMN_ENFORCED', 'Q', 'PAGE_ENFORCED') LOAD_UNIT,
  MAP(D9L.PUFFERUNG, '', '', 'P', 'SINGLE', 'G', 'GNERIC' || CHAR(32) || '(' || LTRIM(D9L.SCHFELDANZ, '0') || ')', 'X', 'FULL', D9L.PUFFERUNG) BUFFER,
  MAP(D9L.BUFALLOW, 'N', 'NO', 'X', 'YES', 'A', 'YES', D9L.BUFALLOW) BUFF_ALLOWED,
  D9L.PROTOKOLL LOG,
  TO_VARCHAR(TO_DATE(D9L.AS4DATE || D9L.AS4TIME, 'YYYYMMDDHH24MISS'), 'YYYY/MM/DD HH24:MI:SS') CHANGE_DATE,
  D9L.AS4USER CHANGE_USER,
  ( SELECT MAX(DDTEXT) FROM DD02T D2T WHERE D2T.TABNAME = D9L.TABNAME AND D2T.DDLANGUAGE = 'E' ) DESCRIPTION
FROM
( SELECT                /* Modification section */
    'ARFC%' TABLE_NAME,
    '%' STORE,
    '%' LOAD_UNIT,
    '%' TABLE_LOGGING
  FROM
    DUMMY
) BI,
  DD09L D9L
WHERE
  D9L.TABNAME LIKE BI.TABLE_NAME AND
  MAP(D9L.ROWORCOLST, 'R', 'ROW', 'C', 'COLUMN', 'UNDEFINED') LIKE BI.STORE AND
  MAP(D9L.LOAD_UNIT, '', 'COLUMN_PREFERRED', 'P', 'PAGE_PREFERRED', 'A', 'COLUMN_ENFORCED', 'Q', 'PAGE_ENFORCED') LIKE BI.LOAD_UNIT AND
  D9L.PROTOKOLL LIKE BI.TABLE_LOGGING
ORDER BY
  D9L.TABNAME