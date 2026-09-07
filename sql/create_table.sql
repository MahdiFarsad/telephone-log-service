-- Run this in a dedicated database/schema, separate from MEAS05 and
-- the audit log service's own tables (per roadmap §2.1).

CREATE TABLE dbo.tblCallLog
(
    ID                  BIGINT IDENTITY(1,1) NOT NULL,
    CallId              NVARCHAR(64)     NOT NULL,
    Direction           NVARCHAR(20)     NOT NULL,
    CallerNumber        NVARCHAR(32)         NULL,
    CalleeNumber        NVARCHAR(32)         NULL,
    CallType            NVARCHAR(20)         NULL,  -- Simotel's "type" field (e.g. "local"); stored for reference, not yet used for Direction
    Queue               NVARCHAR(32)         NULL,
    StartTime           DATETIME2(3)     NOT NULL,
    RingTime            DATETIME2(3)         NULL,
    AnswerTime          DATETIME2(3)         NULL,
    EndTime             DATETIME2(3)     NOT NULL,
    Duration            INT                  NULL,  -- present on NO ANSWER calls; NULL on answered calls
    BillSec             INT                  NULL,  -- present on ANSWERED calls; NULL on no-answer calls
    Wait                INT                  NULL,  -- ring/wait time in seconds
    EntryPoint          NVARCHAR(64)         NULL,  -- inbound gateway name, when present
    OutgoingPoint       NVARCHAR(64)         NULL,  -- outbound gateway name, when present
    Disposition         NVARCHAR(20)     NOT NULL,
    ReceivedAt          DATETIME2(3)     NOT NULL,

    CONSTRAINT PK_tblCallLog PRIMARY KEY CLUSTERED (ID),
    CONSTRAINT UQ_tblCallLog_CallId UNIQUE (CallId)
);

CREATE INDEX IX_CallLog_StartTime
    ON dbo.tblCallLog (StartTime DESC) INCLUDE (Direction, Disposition);

CREATE INDEX IX_CallLog_CallerNumber
    ON dbo.tblCallLog (CallerNumber, StartTime DESC);

CREATE INDEX IX_CallLog_CalleeNumber
    ON dbo.tblCallLog (CalleeNumber, StartTime DESC);

CREATE INDEX IX_CallLog_Direction
    ON dbo.tblCallLog (Direction, StartTime DESC);
