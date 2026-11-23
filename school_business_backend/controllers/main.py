from urllib.parse import quote

from odoo import http
from odoo.http import request


class SchoolGradeExportController(http.Controller):

    @http.route('/school/grade_export/<int:wizard_id>', type='http', auth='user')
    def download_grade_export(self, wizard_id, **kwargs):
        wizard = request.env['school.grade.export.wizard'].browse(wizard_id).exists()
        if not wizard:
            return request.not_found()
        content, filename = wizard._get_xlsx()
        return request.make_response(content, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', "attachment; filename*=UTF-8''%s" % quote(filename)),
        ])
