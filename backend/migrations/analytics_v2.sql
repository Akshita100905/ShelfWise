-- Run once against an existing MySQL database before deploying analytics v2.
-- Back up the database first. Do not run this more than once.
ALTER TABLE purchase_history
  ADD COLUMN price_per_unit DOUBLE NULL,
  ADD COLUMN wasted_quantity DOUBLE NOT NULL DEFAULT 0,
  ADD COLUMN is_demo TINYINT(1) NOT NULL DEFAULT 0;

-- Preserve legacy records that used only the was_wasted boolean.
UPDATE purchase_history
SET wasted_quantity = quantity
WHERE was_wasted = 1 AND wasted_quantity = 0;
