SELECT json_build_object(
    'tenants', (SELECT count(*) FROM tenants),
    'users', (SELECT count(*) FROM users),
    'vehicles', (SELECT count(*) FROM vehicles),
    'drivers', (SELECT count(*) FROM drivers),
    'contracts', (SELECT count(*) FROM contracts),
    'trips', (SELECT count(*) FROM trips),
    'third_parties', (SELECT count(*) FROM third_parties),
    'supplier_invoices', (SELECT count(*) FROM supplier_invoices),
    'supplier_payments', (SELECT count(*) FROM supplier_payments),
    'journal_entries', (SELECT count(*) FROM accounting_journal_entries),
    'journal_items', (SELECT count(*) FROM accounting_journal_items),
    'journal_debit', (
        SELECT coalesce(sum(debit), 0)::text FROM accounting_journal_items
    ),
    'journal_credit', (
        SELECT coalesce(sum(credit), 0)::text FROM accounting_journal_items
    )
)::text;
