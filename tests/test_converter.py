import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import convert_query


def test_migration_sample_script():
    sql = """USE SalesDB;
GO

PRINT 'Starting migration...';
GO

CREATE TABLE dbo.[Employees]
(
    [EmployeeID] INT IDENTITY(1,1) PRIMARY KEY,
    [EmployeeGuid] UNIQUEIDENTIFIER DEFAULT NEWID(),
    [FirstName] NVARCHAR(100) NOT NULL,
    [LastName] NVARCHAR(100) NOT NULL,
    [Email] NVARCHAR(255),
    [Salary] MONEY,
    [IsActive] BIT DEFAULT 1,
    [CreatedDate] DATETIME DEFAULT GETDATE()
);
GO

INSERT INTO dbo.[Employees]
(
    [FirstName],
    [LastName],
    [Email],
    [Salary]
)
VALUES
('John','Doe','john@test.com',55000),
('Jane','Smith','jane@test.com',62000),
('Robert','Brown',NULL,70000);
GO

DECLARE @MinimumSalary MONEY = 60000;

SELECT TOP 5
    EmployeeID,
    FirstName,
    LastName,
    ISNULL(Email,'No Email') AS Email,
    Salary,
    LEN(FirstName) AS NameLength,
    GETDATE() AS CurrentDate
FROM dbo.[Employees]
WHERE Salary > @MinimumSalary
ORDER BY Salary DESC;
GO

SELECT *
FROM dbo.[Employees]
ORDER BY EmployeeID
OFFSET 2 ROWS
FETCH NEXT 3 ROWS ONLY;
GO

SELECT
    EmployeeID,
    CAST(Salary AS INT) AS SalaryInt,
    CONVERT(VARCHAR(10),CreatedDate,120) AS CreatedDate
FROM dbo.[Employees];
GO

SELECT *
INTO #ActiveEmployees
FROM dbo.[Employees]
WHERE IsActive = 1;
GO

UPDATE E
SET Salary = Salary + 5000
FROM dbo.[Employees] E
WHERE E.EmployeeID IN
(
    SELECT EmployeeID
    FROM #ActiveEmployees
);
GO

MERGE dbo.[Employees] AS Target
USING
(
    SELECT
        2 AS EmployeeID,
        'Jane' AS FirstName,
        'Johnson' AS LastName,
        75000 AS Salary
) AS Source
ON Target.EmployeeID = Source.EmployeeID

WHEN MATCHED THEN
UPDATE SET
    Target.LastName = Source.LastName,
    Target.Salary = Source.Salary

WHEN NOT MATCHED THEN
INSERT
(
    FirstName,
    LastName,
    Salary
)
VALUES
(
    Source.FirstName,
    Source.LastName,
    Source.Salary
);
GO

DROP TABLE #ActiveEmployees;
GO

PRINT 'Migration completed successfully.';
GO"""

    converted, warnings = convert_query(sql)

    assert 'AUTO_INCREMENT' in converted
    assert 'UUID()' in converted or 'CURRENT_TIMESTAMP' in converted
    assert 'LIMIT 5' in converted
    assert 'LIMIT 3 OFFSET 2' in converted or 'OFFSET 2' in converted
    assert 'CREATE TEMPORARY TABLE' in converted
    assert 'ON DUPLICATE KEY UPDATE' in converted or 'MERGE' not in converted
    assert 'CHAR_LENGTH' in converted or 'TRIM' in converted


def test_common_tsql_features():
    sql = """
    SELECT
        CASE WHEN Age > 30 THEN 'Senior' ELSE 'Junior' END AS Category,
        REPLACE(Name, 'A', 'X') AS ReplacedName,
        SUBSTRING(Email, 1, 5) AS Prefix,
        CHARINDEX('a', Email) AS Pos,
        STUFF(Email, 1, 1, 'X') AS Stuffed,
        DATEPART(YEAR, CreatedDate) AS YearPart
    FROM Users U
    LEFT JOIN Roles R ON U.RoleId = R.Id
    ;
    """

    converted, warnings = convert_query(sql)

    assert 'CASE' in converted
    assert 'LEFT JOIN' in converted
    assert 'REPLACE' in converted
    assert 'SUBSTRING' in converted
    assert 'LOCATE' in converted
    assert 'YEAR(' in converted or 'DATEPART' not in converted
    assert isinstance(warnings, list)


def test_update_from_is_preserved_with_warning():
    sql = """UPDATE E
SET Salary = Salary + 5000
FROM dbo.[Employees] E
WHERE E.EmployeeID IN
(
    SELECT EmployeeID
    FROM #ActiveEmployees
);"""

    converted, warnings = convert_query(sql)

    assert 'UPDATE E' in converted
    assert 'FROM dbo.[Employees] E' in converted
    assert any('UPDATE ... FROM' in warning for warning in warnings)
    assert isinstance(warnings, list)


def test_regression_for_common_sql_server_issues():
    sql = """USE SalesDB;
GO

PRINT 'Starting migration...';
GO

CREATE TABLE dbo.[Employees]
(
    [EmployeeID] INT IDENTITY(1,1) PRIMARY KEY,
    [FirstName] NVARCHAR(100) NOT NULL,
    [LastName] NVARCHAR(100) NOT NULL,
    [Email] NVARCHAR(255),
    [Salary] MONEY,
    [IsActive] BIT DEFAULT 1,
    [CreatedDate] DATETIME DEFAULT GETDATE()
);
GO

INSERT INTO dbo.[Employees]
(
    [FirstName],
    [LastName],
    [Email],
    [Salary]
)
VALUES
('John','Doe','john@test.com',55000),
('Jane','Smith','jane@test.com',62000);
GO

DECLARE @MinimumSalary MONEY = 60000;

SELECT TOP 5
    EmployeeID,
    FirstName,
    LastName,
    ISNULL(Email,'No Email') AS Email,
    Salary,
    LEN(FirstName) AS NameLength,
    GETDATE() AS CurrentDate
FROM dbo.[Employees]
WHERE Salary > @MinimumSalary
ORDER BY Salary DESC;
GO

SELECT
    EmployeeID,
    CAST(Salary AS INT) AS SalaryInt,
    CONVERT(VARCHAR(10),CreatedDate,120) AS CreatedDate
FROM dbo.[Employees];
GO

SELECT *
INTO #ActiveEmployees
FROM dbo.[Employees]
WHERE IsActive = 1;
GO

UPDATE E
SET Salary = Salary + 5000
FROM dbo.[Employees] E
WHERE E.EmployeeID IN
(
    SELECT EmployeeID
    FROM #ActiveEmployees
);
GO

MERGE dbo.[Employees] AS Target
USING
(
    SELECT
        2 AS EmployeeID,
        'Jane' AS FirstName,
        'Johnson' AS LastName,
        75000 AS Salary
) AS Source
ON Target.EmployeeID = Source.EmployeeID

WHEN MATCHED THEN
UPDATE SET
    Target.LastName = Source.LastName,
    Target.Salary = Source.Salary

WHEN NOT MATCHED THEN
INSERT
(
    FirstName,
    LastName,
    Salary
)
VALUES
(
    Source.FirstName,
    Source.LastName,
    Source.Salary
);
GO

PRINT 'Migration completed successfully.';
GO"""

    converted, warnings = convert_query(sql)

    assert converted.startswith('USE')
    assert 'PRINT' not in converted
    assert "'john@test.com'" in converted
    assert 'SET @MinimumSalary := 60000;' in converted
    assert 'CAST(Salary AS SIGNED)' in converted
    assert 'DATE_FORMAT(CreatedDate' in converted
    assert 'SET Salary = Salary + 5000' in converted
    assert 'FROM ActiveEmployees' in converted
    assert 'ON DUPLICATE KEY UPDATE' in converted
    assert 'LIMIT 5' in converted
