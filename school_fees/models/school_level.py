from odoo import fields, models


class SchoolLevel(models.Model):
    _inherit = 'school.level'

    fee_line_ids = fields.One2many('school.fee.line', 'level_id', string="Tuition Fees")
