def migrate(cr, version):
    """The tuition line now holds the total of the year (it was the amount of each installment),
    and the product moves to the company settings."""
    cr.execute("SELECT 1 FROM information_schema.columns "
               "WHERE table_name = 'school_fee_line' AND column_name = 'installments'")
    if not cr.fetchone():
        return
    cr.execute("UPDATE school_fee_line SET amount = amount * installments")
    cr.execute("SELECT product_id FROM school_fee_line WHERE product_id IS NOT NULL "
               "ORDER BY id LIMIT 1")
    row = cr.fetchone()
    if row:
        cr.execute("""
            INSERT INTO ir_config_parameter (key, value, create_date, write_date)
            VALUES ('school_fees.migrate_product_id', %s, now(), now())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (str(row[0]),))
    # Several lines per level and year are no longer allowed: keep the first one
    cr.execute("""
        DELETE FROM school_fee_line l USING school_fee_line k
        WHERE l.level_id = k.level_id AND l.school_year_id = k.school_year_id
          AND l.company_id = k.company_id AND l.id > k.id
    """)
