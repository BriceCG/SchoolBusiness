{
    'name': "School Admissions Website",
    'version': '18.0.1.0.0',
    'category': 'Education',
    'summary': "Let visitors apply for admission from the website, without an account",
    'description': """
School Admissions Website
=========================
Adds a public admission form to the website:

* Step 1: the visitor fills in the student, address, parent/guardian and schooling information
* Step 2: the visitor uploads the application document and submits the file
* The request is created in the backend and follows the usual admission stages
""",
    'author': "Brice",
    'website': '',
    'depends': ['school_business_backend', 'school_fees', 'website'],
    'data': [
        'views/admission_templates.xml',
        'views/school_admission_views.xml',
        'views/res_partner_views.xml',
        'views/dashboard_templates.xml',
        'views/website_menus.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'school_business_frontend/static/src/js/admission_form.js',
            'school_business_frontend/static/src/css/dashboard.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
