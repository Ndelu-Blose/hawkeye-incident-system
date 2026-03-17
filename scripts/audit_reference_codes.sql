-- Run these queries against your database BEFORE applying the reference_code migration.
-- Record the results; they determine whether the migration can proceed (no duplicates, etc.).

-- 1. How many incidents exist total?
SELECT COUNT(*) AS total_incidents FROM incidents;

-- 2. How many have a NULL or empty reference_no?
SELECT COUNT(*) AS null_or_empty_ref
FROM incidents
WHERE reference_no IS NULL OR reference_no = '';

-- 3. Are there any duplicates already?
SELECT reference_no, COUNT(*)
FROM incidents
WHERE reference_no IS NOT NULL AND reference_no != ''
GROUP BY reference_no
HAVING COUNT(*) > 1;

-- 4. What does the current column definition look like?
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'incidents'
  AND column_name = 'reference_no';
