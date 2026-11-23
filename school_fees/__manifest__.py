{
    'name': "School Fees Invoicing",
    'version': '18.0.1.1.0',
    'category': 'Education',
    'summary': "Define the tuition fees by level and create the student invoices automatically",
    'description': """
School Fees Invoicing
=====================
This module allows you to:

* Define the tuition fees of each school level, school year by school year
  (tuition amount of the year)
* Generate the invoices of the students automatically (draft invoices to review and validate)
* Choose who pays for each student (parent/guardian) and how many payments, and follow the invoices from the student
""",
    'author': "Brice",
    'website': '',
    'depends': ['school_business_backend', 'account'],
    'data': [
        'security/school_fees_security.xml',
        'security/ir.model.access.csv',
        'data/school_fees_data.xml',
        'data/school_fees_reminder_data.xml',
        'wizard/school_fee_invoice_wizard_views.xml',
        'views/res_config_settings_views.xml',
        'views/school_level_views.xml',
        'views/school_student_views.xml',
        'views/account_move_views.xml',
        'views/school_fees_menus.xml',
        'views/school_fee_reminder_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
