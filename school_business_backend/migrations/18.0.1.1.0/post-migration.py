from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Create a school.year for every academic year already used (stored as "2025-2026")
    and link the existing admissions, classrooms and students to it."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Year = env['school.year']
    for table in ('school_admission', 'school_classroom', 'school_student'):
        cr.execute(
            f"SELECT DISTINCT company_id, academic_year FROM {table} "  # noqa: S608
            "WHERE school_year_id IS NULL AND academic_year IS NOT NULL")
        for company_id, name in cr.fetchall():
            year = Year.search([('name', '=', name), ('company_id', '=', company_id)], limit=1)
            if not year:
                try:
                    start = int(name.split('-')[0])
                except ValueError:
                    continue
                year = Year.create({
                    'name': name,
                    'company_id': company_id,
                    'date_start': '%s-09-01' % start,
                    'date_end': '%s-08-31' % (start + 1),
                })
            cr.execute(
                f"UPDATE {table} SET school_year_id = %s "  # noqa: S608
                "WHERE company_id = %s AND academic_year = %s AND school_year_id IS NULL",
                (year.id, company_id, name))
