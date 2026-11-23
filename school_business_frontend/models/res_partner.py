from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_student = fields.Boolean(
        string="Is a Student", copy=False, readonly=True,
        help="Set automatically once the admission of the contact is successful (enrolled).")
