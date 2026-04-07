SELECT

/* 

[NAME]

- HANA_ABAP_Parameters_ClientCopy

[DESCRIPTION]

- ABAP client copy expert parameter settings

[SOURCE]

- SAP Note 1969700

[DETAILS AND RESTRICTIONS]

- Needs to be run as ABAP schema owner as access to ABAP table data is required, otherwise an error like the following is reported:

  [259]: invalid table name:  Could not find table/view <table> in schema <schema>

- If access to ABAP objects is possible but you cannot log on as ABAP user, you can switch the default schema before executing the command:

  SET SCHEMA SAP<sid>

[VALID FOR]

- Revisions:              all
- Client application:     ABAP

[SQL COMMAND VERSION]

- 2023/12/31:  1.0 (initial version)

[INVOLVED TABLES]

- CCOPTION

[INPUT PARAMETERS]

  ABAP client copy option / parameter

  'LARGEBLOCK' --> Only consider ABAP client copy option LARGEBLOCK
  '%CURS'      --> Only consider ABAP client copy options ending with 'CURS'
  '%'          --> No restriction related to ABAP client copy options

- ACTIVE

  ABAP parameter value

  'X'          --> Only display active client copy options
  ' '          --> Only display inactive client copy options
  '%'          --> Display all client copy options

[OUTPUT PARAMETERS]

- OPTION: Client copy option / parameter
- ACTIVE: 'X' if option is active, otherwise ' '

[EXAMPLE OUTPUT]

-------------------
|OPTION    |ACTIVE|
-------------------
|390OPT    |      |
|AUTO_MAIL |      |
|CHK_ASSIGN|      |
|CWITH_CURS|X     |
|DEBUG_INFO|X     |
|DWITH_CURS|X     |
|IGNORE_CON|X     |
|KEY_DELETE|      |
|LARGEBLOCK|X     |
|LOCK_SYS  |X     |
|MAX_WPRUN |X     |
|NATIVECOPY|X     |
|NOEXPORT  |      |
|NO_CHECK  |X     |
|NO_REL_CHK|      |
|NO_RFCCHK |X     |
|SINGLECOPY|X     |
|SKIP_EMPTY|X     |
|SMALLBLOCK|X     |
|SRC_LOCK  |      |
|VERIFY_CNT|X     |
-------------------

*/

  O.COPTION OPTION,
  O.ACTIVE
FROM
( SELECT         /* Modification section */
    '%' OPTION,
    '%' ACTIVE
  FROM
    DUMMY
) BI,
  CCOPTION O
WHERE
  O.COPTION LIKE BI.OPTION AND
  O.ACTIVE LIKE BI.ACTIVE
ORDER BY
  O.COPTION