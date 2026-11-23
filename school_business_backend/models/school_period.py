from odoo import fields, models

PERIOD_TYPES = [
    ('term', "Term (3 per year)"),
    ('semester', "Semester (2 per year)"),
    ('bimester', "Bimester (6 per year)"),
]


class SchoolPeriod(models.Model):
    _name = 'school.period'
    _description = "Grading Period"
    _order = 'period_type, sequence, id'

    name = fields.Char(string="Period", required=True, translate=True)
    period_type = fields.Selection(PERIOD_TYPES, string="Period Type", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_type_unique', 'unique(name, period_type)',
         "This period already exists for this period type."),
    ]
