{
    'name': "School Admissions Management",
    'version': '18.0.1.1.0',
    'category': 'Education',
    'summary': "Manage student admission requests for a school",
    'description': """
School Admissions Management
=============================
This module allows you to:

* Register student admission requests with their basic information
  (identity, date of birth, address, parent/guardian, requested level, ...)
* Track each application through the admission stages: New, Application Submitted,
  Interview, Entrance Exam, Accepted, Enrolled or Refused
* Manage the school levels/grades offered by the school
* Schedule interviews and entrance exams and keep a history of the communication
""",
    'author': "Brice",
    'website': '',
    'depends': ['base', 'mail', 'portal'],
    'data': [
        'security/school_security.xml',
        'security/ir.model.access.csv',
        'data/school_sequence_data.xml',
        'data/school_level_data.xml',
        'data/school_period_data.xml',
        'data/school_mail_activity_type_data.xml',
        'views/school_year_views.xml',
        'views/school_level_views.xml',
        'views/school_admission_views.xml',
        'views/school_subject_views.xml',
        'views/school_classroom_views.xml',
        'views/school_student_views.xml',
        'views/school_teacher_views.xml',
        'views/school_timetable_views.xml',
        'views/school_grade_views.xml',
        'views/res_config_settings_views.xml',
        'views/school_menus.xml',
        'wizard/school_admission_wizard_views.xml',
        'wizard/school_grade_export_wizard_views.xml',
        'report/school_report_card.xml',
        'report/school_timetable_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'school_business_backend/static/src/timetable_calendar/timetable_calendar.js',
            'school_business_backend/static/src/timetable_calendar/timetable_calendar.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
