from odoo import fields, models


class SchoolSubject(models.Model):
    _name = 'school.subject'
    _description = "Subject"
    _order = 'sequence, name'

    name = fields.Char(string="Subject", required=True, translate=True)
    code = fields.Char(string="Code", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    coefficient = fields.Float(
        string="Coefficient", default=1.0, required=True,
        help="Weight of the subject in the student average.")
    level_ids = fields.Many2many(
        'school.level', string="Levels",
        help="Levels in which this subject is taught.")
    description = fields.Text(string="Description")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', "The subject code must be unique."),
        ('coefficient_positive', 'check(coefficient > 0)', "The coefficient must be strictly positive."),
    ]
