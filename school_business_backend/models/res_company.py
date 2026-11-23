from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .school_period import PERIOD_TYPES


class ResCompany(models.Model):
    _inherit = 'res.company'

    school_period_type = fields.Selection(
        PERIOD_TYPES, string="Grading Periods", required=True, default='term',
        help="How the school year is divided to record the grades: "
             "terms (3 periods of 3 months), semesters (2 periods of 6 months) "
             "or bimesters (6 periods of 2 months).")
    current_school_year_id = fields.Many2one(
        'school.year', string="Current School Year", copy=False,
        domain="[('state', '=', 'open')]",
        help="All the new school data (admissions, classrooms, students) follow this school year.")

    @api.constrains('current_school_year_id')
    def _check_current_school_year(self):
        for company in self:
            year = company.current_school_year_id
            if year and year.state == 'closed':
                raise ValidationError(self.env._("A closed school year cannot be the current year."))
