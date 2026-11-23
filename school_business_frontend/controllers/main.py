import base64
import os
from datetime import datetime

from odoo import _, fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import consteq, email_normalize

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
MAX_PHOTO_SIZE = 5 * 1024 * 1024
DOCUMENT_EXTENSIONS = ('.pdf', '.jpg', '.jpeg', '.png')
PHOTO_EXTENSIONS = ('.jpg', '.jpeg', '.png')

TEXT_FIELDS = (
    'student_name', 'student_email', 'place_of_birth', 'street', 'street2', 'city', 'zip',
    'parent_name', 'parent_phone', 'parent_email', 'previous_school',
    'previous_level',
)


class SchoolAdmissionWebsite(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_admission(self, admission_id, token):
        """Return the admission matching the access token, or an empty recordset."""
        admission = request.env['school.admission'].sudo().browse(admission_id).exists()
        if not admission or not token or not admission.access_token \
                or not consteq(admission.access_token, token):
            return request.env['school.admission'].sudo()
        return admission

    @staticmethod
    def _admission_to_form(admission):
        """Return the values of an existing admission as the form dict of the template."""
        form = {key: admission[key] or '' for key in TEXT_FIELDS}
        form.update({
            'date_of_birth': admission.date_of_birth.isoformat() if admission.date_of_birth else '',
            'gender': admission.gender or '',
            'parent_relationship': admission.parent_relationship or '',
            'level_id': str(admission.level_id.id or ''),
            'school_year_id': str(admission.school_year_id.id or ''),
            'nationality_id': str(admission.nationality_id.id or ''),
            'country_id': str(admission.country_id.id or ''),
            'state_id': str(admission.state_id.id or ''),
        })
        return form

    def _form_context(self, form=None, errors=None, admission=None, token=None):
        env = request.env
        return {
            'form_action': (
                '/admission/%s/edit/submit' % admission.id if admission
                else '/admission/apply/submit'),
            'token': token,
            'levels': env['school.level'].sudo().search([]),
            'countries': env['res.country'].sudo().search([]),
            'states': env['res.country.state'].sudo().search([]),
            'school_years': env['school.year'].sudo().search([('state', '=', 'open')]),
            'default_year_id': str(env.company.sudo().current_school_year_id.id or ''),
            'form': form or {},
            'errors': errors or {},
        }

    @staticmethod
    def _read_upload(upload, extensions, max_size, label):
        """Return (base64 content, filename) of an uploaded file after validation."""
        filename = os.path.basename(upload.filename or '')
        if not filename.lower().endswith(extensions):
            raise ValidationError(_(
                "%(label)s: allowed formats are %(formats)s.",
                label=label, formats=', '.join(extensions)))
        content = upload.read()
        if not content:
            raise ValidationError(_("%s is empty.", label))
        if len(content) > max_size:
            raise ValidationError(_(
                "%(label)s is too large (maximum %(size)s MB).",
                label=label, size=max_size // (1024 * 1024)))
        return base64.b64encode(content), filename

    def _prepare_vals(self, post, files, admission=None):
        """Validate the submitted form and return (create values, errors)."""
        errors = {}
        form = {key: (post.get(key) or '').strip() for key in TEXT_FIELDS}
        for key in ('date_of_birth', 'level_id', 'school_year_id', 'gender', 'nationality_id', 'country_id',
                    'state_id', 'parent_relationship'):
            form[key] = (post.get(key) or '').strip()

        required_fields = {
            'student_name': _("Student name"),
            'student_email': _("Student email"),
            'date_of_birth': _("Date of birth"),
            'level_id': _("Requested level"),
            'school_year_id': _("Academic year"),
            'parent_name': _("Parent/Guardian name"),
            'parent_phone': _("Parent phone"),
        }
        for key, label in required_fields.items():
            if not form.get(key):
                errors[key] = _("%s is required.", label)

        for key in ('student_email', 'parent_email'):
            if form[key] and not email_normalize(form[key]):
                errors[key] = _("Please enter a valid email address.")

        vals = {key: form[key] or False for key in TEXT_FIELDS}

        if form['student_email'] and 'student_email' not in errors:
            duplicate = request.env['school.admission'].sudo().with_context(active_test=False).search_count([
                ('student_email', '=ilike', form['student_email']),
                ('id', '!=', admission.id if admission else 0),
            ])
            if duplicate:
                errors['student_email'] = _(
                    "An admission request already exists for this email address.")

        if form['date_of_birth'] and 'date_of_birth' not in errors:
            try:
                dob = datetime.strptime(form['date_of_birth'], '%Y-%m-%d').date()
            except ValueError:
                errors['date_of_birth'] = _("Please enter a valid date.")
            else:
                if dob >= fields.Date.context_today(request.env['school.admission']):
                    errors['date_of_birth'] = _("The date of birth must be in the past.")
                vals['date_of_birth'] = dob

        Level = request.env['school.level'].sudo()
        if form['level_id'].isdigit() and Level.search([('id', '=', int(form['level_id']))]):
            vals['level_id'] = int(form['level_id'])
        elif 'level_id' not in errors:
            errors['level_id'] = _("Please select a valid level.")

        SchoolYear = request.env['school.year'].sudo()
        if form['school_year_id'].isdigit() and SchoolYear.search([
                ('id', '=', int(form['school_year_id'])), ('state', '=', 'open')]):
            vals['school_year_id'] = int(form['school_year_id'])
        elif 'school_year_id' not in errors:
            errors['school_year_id'] = _("Please select a valid academic year.")

        if form['gender'] in ('male', 'female'):
            vals['gender'] = form['gender']
        if form['parent_relationship'] in ('father', 'mother', 'guardian'):
            vals['parent_relationship'] = form['parent_relationship']

        country_ids = set(request.env['res.country'].sudo().search([]).ids)
        for key in ('nationality_id', 'country_id'):
            if form[key].isdigit() and int(form[key]) in country_ids:
                vals[key] = int(form[key])
        if form['state_id'].isdigit():
            state = request.env['res.country.state'].sudo().browse(int(form['state_id'])).exists()
            if state and state.country_id.id == vals.get('country_id'):
                vals['state_id'] = state.id

        photo = files.get('photo')
        if photo and photo.filename:
            try:
                vals['photo'], _filename = self._read_upload(
                    photo, PHOTO_EXTENSIONS, MAX_PHOTO_SIZE, _("Photo"))
            except ValidationError as e:
                errors['photo'] = e.args[0]

        return form, vals, errors

    # ------------------------------------------------------------------
    # Step 1: admission information
    # ------------------------------------------------------------------
    @http.route('/admission', type='http', auth='public', website=True, sitemap=False)
    def admission_index(self, **kw):
        return request.redirect('/admission/apply')

    @http.route('/admission/apply', type='http', auth='public', website=True, sitemap=True)
    def admission_apply(self, **kw):
        return request.render('school_business_frontend.admission_form', self._form_context())

    @http.route('/admission/apply/submit', type='http', auth='public', website=True,
                methods=['POST'], sitemap=False)
    def admission_apply_submit(self, **post):
        form, vals, errors = self._prepare_vals(post, request.httprequest.files)
        if errors:
            return request.render(
                'school_business_frontend.admission_form', self._form_context(form, errors))

        vals.update({
            'company_id': request.website.company_id.id,
            # nobody is logged in: do not assign the request to the public user
            'responsible_id': False,
        })
        Admission = request.env['school.admission'].sudo()
        try:
            with request.env.cr.savepoint():
                admission = Admission.create(vals)
        except (ValidationError, UserError):
            errors['general'] = _("Your request could not be registered. Please check your information.")
            return request.render(
                'school_business_frontend.admission_form', self._form_context(form, errors))

        token = admission._portal_ensure_token()
        return request.redirect('/admission/%s/document?token=%s' % (admission.id, token))

    # ------------------------------------------------------------------
    # Completion of an existing request (link sent from the backend)
    # ------------------------------------------------------------------
    @http.route('/admission/<int:admission_id>/edit', type='http', auth='public',
                website=True, sitemap=False)
    def admission_edit(self, admission_id, token=None, **kw):
        admission = self._get_admission(admission_id, token)
        if not admission:
            return request.redirect('/admission/apply')
        if admission.state != 'draft':
            return request.redirect('/admission/%s/done?token=%s' % (admission.id, token))
        return request.render('school_business_frontend.admission_form', self._form_context(
            self._admission_to_form(admission), admission=admission, token=token))

    @http.route('/admission/<int:admission_id>/edit/submit', type='http', auth='public',
                website=True, methods=['POST'], sitemap=False)
    def admission_edit_submit(self, admission_id, token=None, **post):
        admission = self._get_admission(admission_id, token)
        if not admission:
            return request.redirect('/admission/apply')
        if admission.state != 'draft':
            return request.redirect('/admission/%s/done?token=%s' % (admission.id, token))

        form, vals, errors = self._prepare_vals(post, request.httprequest.files, admission)
        if not errors:
            try:
                with request.env.cr.savepoint():
                    admission.write(vals)
            except (ValidationError, UserError):
                errors['general'] = _(
                    "Your request could not be registered. Please check your information.")
        if errors:
            return request.render('school_business_frontend.admission_form', self._form_context(
                form, errors, admission=admission, token=token))
        return request.redirect('/admission/%s/document?token=%s' % (admission.id, token))

    # ------------------------------------------------------------------
    # Step 2: application document
    # ------------------------------------------------------------------
    @http.route('/admission/<int:admission_id>/document', type='http', auth='public',
                website=True, sitemap=False)
    def admission_document(self, admission_id, token=None, **kw):
        admission = self._get_admission(admission_id, token)
        if not admission:
            return request.redirect('/admission/apply')
        if admission.state != 'draft':
            return request.redirect('/admission/%s/done?token=%s' % (admission.id, token))
        return request.render('school_business_frontend.admission_document', {
            'admission': admission,
            'token': token,
            'error': kw.get('error'),
            'has_document': bool(admission.application_document),
        })

    @http.route('/admission/<int:admission_id>/document/submit', type='http', auth='public',
                website=True, methods=['POST'], sitemap=False)
    def admission_document_submit(self, admission_id, token=None, **post):
        admission = self._get_admission(admission_id, token)
        if not admission:
            return request.redirect('/admission/apply')
        if admission.state != 'draft':
            return request.redirect('/admission/%s/done?token=%s' % (admission.id, token))

        upload = request.httprequest.files.get('application_document')
        error = None
        if not upload or not upload.filename:
            if admission.application_document:
                try:
                    admission.action_submit()
                except (ValidationError, UserError) as e:
                    error = e.args[0]
            else:
                error = _("Please attach the application document.")
        else:
            try:
                content, filename = self._read_upload(
                    upload, DOCUMENT_EXTENSIONS, MAX_DOCUMENT_SIZE, _("Application document"))
                admission.write({
                    'application_document': content,
                    'application_document_filename': filename,
                })
                admission.action_submit()
            except (ValidationError, UserError) as e:
                error = e.args[0]
        if error:
            return request.render('school_business_frontend.admission_document', {
                'admission': admission,
                'token': token,
                'error': error,
                'has_document': bool(admission.application_document),
            })
        return request.redirect('/admission/%s/done?token=%s' % (admission.id, token))

    # ------------------------------------------------------------------
    # Confirmation
    # ------------------------------------------------------------------
    @http.route('/admission/<int:admission_id>/done', type='http', auth='public',
                website=True, sitemap=False)
    def admission_done(self, admission_id, token=None, **kw):
        admission = self._get_admission(admission_id, token)
        if not admission:
            return request.redirect('/admission/apply')
        if admission.state == 'draft':
            return request.redirect('/admission/%s/document?token=%s' % (admission.id, token))
        return request.render('school_business_frontend.admission_done', {
            'admission': admission,
        })
