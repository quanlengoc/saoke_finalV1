-- Query B4 data for TOPUP service
-- Parameters: :service_id, :partner_id, :date_from, :date_to

SELECT 
    t.transaction_ref,
    t.partner_ref,
    t.transaction_date,
    t.total_amount,
    t.quantity,
    t.customer_id,
    t.status,
    t.channel
FROM 
    transactions t
WHERE 
    t.service_id = :service_id
    AND t.partner_id = :partner_id
    AND t.transaction_date BETWEEN :date_from AND :date_to
    AND t.status = 'SUCCESS'
ORDER BY 
    t.transaction_date, t.transaction_ref
