from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    teacher_ids = fields.One2many('school.teacher', 'partner_id', string="Teacher Records")
    is_teacher = fields.Boolean(
        string="Is a Teacher", compute='_compute_is_teacher', store=True,
        help="Set automatically when a teacher record is linked to this contact.")

    @api.depends('teacher_ids')
    def _compute_is_teacher(self):
        for partner in self:
            partner.is_teacher = bool(partner.teacher_ids)
