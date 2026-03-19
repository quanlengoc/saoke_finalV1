-- Query thu_ho test data from SQLite
-- Parameters: {date_from}, {date_to}

SELECT *
FROM thu_ho
WHERE 1=1
    AND merchant != '{merchant}'
    AND thoi_gian >= '{date_from}'
    AND thoi_gian < date('{date_to}', '+1 day')
