from odoo import _, fields, models


class SchoolLevel(models.Model):
    _name = 'school.level'
    _description = "School Level"
    _order = 'sequence, name'

    name = fields.Char(string="Level", required=True, translate=True)
    sequence = fields.Integer(string="Sequence", default=10)
    description = fields.Text(string="Description")
    active = fields.Boolean(default=True)
    admission_count = fields.Integer(string="Admission Requests", compute='_compute_admission_count')

    def _compute_admission_count(self):
        for level in self:
            level.admission_count = self.env['school.admission'].search_count(
                [('level_id', '=', level.id)]
            )

    def action_view_admissions(self):
        self.ensure_one()
        return {
            'name': _("Admission Requests"),
            'type': 'ir.actions.act_window',
            'res_model': 'school.admission',
            'view_mode': 'list,kanban,form',
            'domain': [('level_id', '=', self.id)],
            'context': {'default_level_id': self.id},
        }
