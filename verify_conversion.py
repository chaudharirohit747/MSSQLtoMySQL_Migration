import sys
import types
from pathlib import Path

flask_mod = types.ModuleType('flask')

class DummyFlask:
    def __init__(self, *args, **kwargs):
        self.routes = {}
    def route(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def run(self, *args, **kwargs):
        pass

flask_mod.Flask = DummyFlask
flask_mod.jsonify = lambda payload: payload
flask_mod.render_template = lambda *args, **kwargs: ''
flask_mod.request = types.SimpleNamespace(get_json=lambda silent=True: {}, form={})
sys.modules['flask'] = flask_mod

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app import convert_query

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
print(converted)
print('---WARNINGS---')
print('\n'.join(warnings))
