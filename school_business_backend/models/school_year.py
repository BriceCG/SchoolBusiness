from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchoolYear(models.Model):
    _name = 'school.year'
    _description = "School Year"
    _order = 'date_start desc, id desc'

    name = fields.Char(string="School Year", required=True)
    date_start = fields.Date(string="Start Date", required=True)
    date_end = fields.Date(string="End Date", required=True)
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company, required=True)
    state = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed'),
    ], string="Status", default='open', required=True, copy=False)
    is_current = fields.Boolean(string="Current Year", compute='_compute_is_current')

    _sql_constraints = [
        ('name_company_unique', 'unique(name, company_id)',
         "A school year with this name already exists."),
        ('dates_check', 'check(date_end > date_start)',
         "The end date must be after the start date."),
    ]

    @api.depends('company_id.current_school_year_id')
    def _compute_is_current(self):
        for rec in self:
            rec.is_current = rec.company_id.current_school_year_id == rec

    @api.constrains('date_start', 'date_end', 'company_id')
    def _check_overlap(self):
        for rec in self:
            overlap = self.search([
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('date_start', '<=', rec.date_end),
                ('date_end', '>=', rec.date_start),
            ], limit=1)
            if overlap:
                raise ValidationError(_(
                    "The school year %(year)s overlaps with %(other)s.",
                    year=rec.name, other=overlap.name))

    def action_close(self):
        for rec in self:
            if rec.is_current:
                raise UserError(_(
                    "The year %s is the current school year. Select another current year "
                    "in the settings before closing it.", rec.name))
        self.write({'state': 'closed'})

    def action_reopen(self):
        self.write({'state': 'open'})

    def action_set_current(self):
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_("A closed school year cannot be the current year."))
        self.company_id.current_school_year_id = self

    @api.model
    def _get_current(self):
        return self.env.company.current_school_year_id
