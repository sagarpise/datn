from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..utils.google_drive_helper import GoogleDriveHelper


class CrmDocument(models.Model):
    _inherit = 'crm.lead'

    # _name = 'document.crm'
    # name = fields.Char(string='Name', required=True, copy=False, readonly=True, index=True)
    @api.model
    def _compute_is_favorite(self):
        for document in self:
            document.is_favorite = self.env.user in document.favorite_user_ids

    def _inverse_is_favorite(self):
        favorite_document = not_fav_document = self.env['crm.lead'].sudo()
        for document in self:
            if self.env.user in document.favorite_user_ids:
                favorite_document |= document
            else:
                not_fav_document |= document
        # Project User has no write access for project.
        favorite_document.write({'favorite_user_ids': [(3, self.env.uid)]})
        not_fav_document.write({'favorite_user_ids': [(4, self.env.uid)]})
        return True

    def _get_default_favorite_user_ids(self):
        return [(6, 0, [self.env.uid])]

    document_crm_name = fields.Char(string="Folder Name")
    google_drive_url = fields.Char(readonly=True)
    file_id = fields.Char(readonly=True)
    document_crm_part = fields.One2many('document.crm.part', 'document_crm_id',
                                        string='Document Part')
    document_tab_visible = fields.Text(compute='_document_tab_visible')
    favorite_user_ids = fields.Many2many(
        'res.users', 'document_crm_favorite_user_rel', 'document_id', 'user_id',
        string='Favorite Members',
        default=_get_default_favorite_user_ids)
    is_favorite = fields.Boolean(
        string='Show on dashboard',
        compute='_compute_is_favorite', inverse='_inverse_is_favorite',
        help="Favorite teams to display them in the dashboard and access them easily.")

    def _document_tab_visible(self):
        self.ensure_one()
        self.document_tab_visible = False
        if self.user_has_groups('base.group_system') or self.env['crm.lead'].browse(self.id).user_id.id == self._uid:
            self.document_tab_visible = True

    def action_document_crm_list(self):
        # Dung de khoi tao view voi domain chay bang python
        if self.user_has_groups('base.group_system'):
            domain = [('document_crm_name', '!=', False)]
        else:
            self.env.cr.execute(
                """select document_crm_id from document_crm_part where id in  (select res_id from document_permission where res_user_id=%s and model like 'crm' group by res_user_id,res_id)""",
                (self._uid,))
            can_read_documents = self.env.cr.fetchall()
            domain = [('id', 'in', [val[0] for val in can_read_documents])]
        views = [(self.env.ref('document_management.view_document_crm_kanban').id, 'kanban'),
                 (self.env.ref('document_management.view_document_crm_folder').id, 'folder')]
        action = {"name": "CRM Documents", "type": "ir.actions.act_window", "view_mode": "kanban,tree,folder,form,",
                  "view_type": "form",
                  "res_model": "crm.lead", "context": {"create": False}, 'domain': domain, 'view_id': False,
                  'views': views}

        return action

    @api.model
    def create(self, values):

        if values.get('document_crm_name', False):
            Config = self.env['ir.config_parameter'].sudo()
            parent_file_url = Config.get_param('document_management.crm_folder_base')
            parent_file_url_arr = parent_file_url.split('/')
            parent_id = parent_file_url_arr[len(parent_file_url_arr) - 1]
            googleDriveHelper = GoogleDriveHelper()
            google_drive_new_folder = googleDriveHelper.create_sub_file(parent_id,
                                                                        values.get('document_crm_name'))
            values['google_drive_url'] = 'https://drive.google.com/drive/folders/' + google_drive_new_folder['id']
            values['file_id'] = google_drive_new_folder['id']
            folder = super(CrmDocument, self).create(values)
            return folder
        else:
            result = super(CrmDocument, self).create(values)
            return result

            # if self.document_crm_name == False:
            #     googleDriveHelper = GoogleDriveHelper()
            #     googleDriveHelper.deleteFile(self['file_id'])
            #     return super(CrmDocument, self).unlink()

    def write(self, values):
        if values.get('is_favorite'):
            values.pop('is_favorite')
            self._fields['is_favorite'].determine_inverse(self)
        if values.get('document_crm_name'):
            if self.user_has_groups('base.group_system') or self.env['crm.lead'].browse(
                    self.id).user_id.id == self._uid:
                self.env.cr.execute("""select document_crm_name from crm_lead where id=%s""",
                                    (self.id,))
                document_name = self.env.cr.fetchone()

                if document_name[0] is not None:
                    if values.get('document_crm_name') == False:
                        googleDriveHelper = GoogleDriveHelper()
                        googleDriveHelper.deleteFile(self['file_id'])
                        values['google_drive_url'] = False
                        values['file_id'] = False
                        # xoa part
                        delete = self.env['document.crm.part'].sudo().search(
                            [('document_crm_id', '=', self.id)])
                        for e in delete:
                            e.unlink()
                    else:
                        google_drive_helper = GoogleDriveHelper()
                        google_drive_helper.update_file_name(file_id=self['file_id'],
                                                             new_name=values.get('document_crm_name'))
                else:
                    if values.get('document_crm_name'):
                        Config = self.env['ir.config_parameter'].sudo()
                        parent_file_url = Config.get_param('document_management.crm_folder_base')
                        parent_file_url_arr = parent_file_url.split('/')
                        parent_id = parent_file_url_arr[len(parent_file_url_arr) - 1]
                        googleDriveHelper = GoogleDriveHelper()
                        google_drive_new_folder = googleDriveHelper.create_sub_file(parent_id,
                                                                                    values.get(
                                                                                        'document_crm_name'))
                        # values['google_drive_url'] = 'https://drive.google.com/drive/folders/' + \
                        #                              google_drive_new_folder[
                        #                                  'id']
                        # values['file_id'] = google_drive_new_folder['id']
                        base_url = 'https://drive.google.com/drive/folders/' + \
                                   google_drive_new_folder[
                                       'id']
                        file_id = google_drive_new_folder['id']
                        # force update database
                        self.env.cr.execute(
                            """update crm_lead set google_drive_url = %s , file_id = %s WHERE id=%s""", (base_url, file_id, self.id))
                        self.env.cr.commit()
        folder = super(CrmDocument, self).write(values)
        return folder

    def get_crm_document_action_document_part(self, context=None):
        if not context:
            context = self._context
        if self.user_has_groups('base.group_system'):
            domain = [('document_crm_id', '=', context['active_id'])]
        else:
            domain = [('document_crm_id', '=', context['active_id'])]
            self.env.cr.execute(
                """select res_id from document_permission where res_user_id = %s and model like 'crm' group by res_id""",
                (self._uid,))
            can_read_documents = self.env.cr.fetchall()
            domain.append(('id', 'in', [val[0] for val in can_read_documents]))
        action = {"name": self.name, "type": "ir.actions.act_window", "view_mode": "kanban,form",
                  "view_type": "form",
                  "res_model": "document.crm.part", 'domain': domain,
                  "context": {'default_document_crm_id': self.id, "create": True}, }
        return action

    def unlink(self):
        google_drive_helper = GoogleDriveHelper()
        for rec in self:
            try:
                google_drive_helper.deleteFile(rec.file_id)
            except Exception as ex:
                a = 0
        return super(CrmDocument, self).unlink()


class DocumentcrmPart(models.Model):
    _name = "document.crm.part"

    name = fields.Char(required=True)
    document_crm_id = fields.Many2one('crm.lead', inverse_name='id', string='Document',
                                      ondelete='cascade')

    google_drive_url = fields.Char(readonly=True)
    file_id = fields.Char(readonly=True)
    write_users = fields.Many2many('res.users', 'document_crm_part_write_user_rel', 'crm_part_id',
                                   'res_user_id',
                                   string='Write Users', required=True)
    read_users = fields.Many2many('res.users', 'document_crm_part_read_user_rel', 'crm_part_id',
                                  'res_user_id',
                                  string='Read Users', required=True)

    current_permission_can_update = fields.Boolean(compute='_compute_current_permission_can_update', default=False,
                                                   store=False)

    def _compute_current_permission_can_update(self):
        for e in self:
            e.current_permission_can_update = False
            if self.user_has_groups('base.group_system'):
                e['current_permission_can_update'] = True
            elif e.create_uid.id == self._uid:
                e['current_permission_can_update'] = True
            else:
                current_crm_id = self._context.get('default_document_crm_id')
                if current_crm_id:
                    if self.env['crm.lead'].browse(current_crm_id).user_id.id == self._uid:
                        e['current_permission_can_update'] = True

    def get_crm_document_action_document_part_file(self, context=None):
        # check can create file
        # domain = []
        can_create = False
        if not context:
            context = self._context
        # if context:
        if self.user_has_groups('base.group_system'):
            can_create = True
        self.env.cr.execute(
            """select res_user_id from document_crm_part_write_user_rel where res_user_id=%s and crm_part_id=%s """,
            (self._uid, self.ids[0],))
        current_user_permission = self.env.cr.fetchone()
        if current_user_permission is not None and len(current_user_permission) > 0:
            can_create = True
        domain = [('0', '=', '1')]
        if can_create:
            domain = [('res_id', '=', context['active_id'])]
        else:
            self.env.cr.execute(
                """select id from document_permission where res_user_id=%s and model='crm' """,
                (self._uid,))
            found_ids = self.env.cr.fetchone()
            if found_ids and len(found_ids) > 0:
                domain = [('res_id', '=', context['active_id'])]
        action = {"name": self.name, "type": "ir.actions.act_window", "view_mode": "kanban,form,tree",
                  "view_type": "form",
                  "res_model": "document.crm.file",
                  "context": {'default_res_id': self.id, 'create': can_create},
                  'domain': domain}
        return action

    def call_back_parent_root(self):
        action = self.document_crm_id.action_document_crm_list()
        action['target'] = 'main'
        return action

    def call_back_parent_part(self, context=None):
        action = self.document_crm_id.get_crm_document_action_document_part(context)
        action['target'] = 'main'
        return action

    @api.model
    def create(self, values):
        document_crm_id = values.get('document_crm_id')
        if document_crm_id is None:
            document_crm_id = self._context.get('default_document_crm_id')
        can_create = False
        if self.user_has_groups('base.group_system'):
            can_create = True
        if self.env['crm.lead'].browse(document_crm_id).user_id.id == self._uid:
            can_create = True
        self.env.cr.execute(
            """select res_user_id from document_crm_part_write_user_rel where res_user_id=%s and crm_part_id=%s """,
            (self._uid, document_crm_id,))
        current_user_permission = self.env.cr.fetchone()
        if current_user_permission is not None and len(current_user_permission) > 0:
            can_create = True
        if can_create:
            # self.env.cr.execute("""select id from document_crm_part where document_crm_id not in (select id from crm_lead)"""
            #                     )
            # document_quo_id = self.env.cr.fetchone()
            # abc=values.get('document_crm_name')
            # if document_quo_id:
            google_drive_helper = GoogleDriveHelper()
            new_folder = google_drive_helper.create_sub_file(self.env['crm.lead'].sudo().browse(
                document_crm_id).file_id, values.get('name'))
            values['google_drive_url'] = 'https://drive.google.com/drive/folders/' + new_folder['id']
            values['file_id'] = new_folder['id']
            folder = super(DocumentcrmPart, self).create(values)
            # else:
            #
            #     raise UserError(_("You need create parent Folder"))

            if values.get('write_users'):
                for e in values.get('write_users')[0][2]:
                    self.env['document.permission'].sudo().create({
                        'type': 'write',
                        'model': 'crm',
                        'res_id': folder.id,
                        'res_user_id': e,
                    })
            if values.get('read_users'):
                # group_ids = []
                for e in values.get('read_users')[0][2]:
                    if values.get('write_users'):
                        if e not in values.get('write_users')[0][2]:
                            self.env['document.permission'].sudo().create({
                                'type': 'read',
                                'model': 'crm',
                                'res_id': folder.id,
                                'res_user_id': e,
                            })
                    else:
                        self.env['document.permission'].sudo().create({
                            'type': 'read',
                            'model': 'crm',
                            'res_id': folder.id,
                            'res_user_id': e,
                        })
            return folder
        else:
            raise UserError(_("You don't have permission to do this action"))

    def write(self, values):
        folder = super(DocumentcrmPart, self).write(values)
        self.env.cr.execute(
            """select res_user_id from document_crm_part_write_user_rel where crm_part_id = %s""",
            (self.id,))
        all_write_user_ids = self.env.cr.fetchall()
        # liet ke tat ca ca user co quyen write
        if values.get('write_users') or values.get('read_users'):

            self.env['document.permission'].sudo().search(
                [('model', 'like', 'crm'), ('type', 'like', 'write'), ('res_id', '=', self.id),
                 ('res_user_id', 'not in', tuple(e[0] for e in all_write_user_ids))]).unlink()
            # xoa tat ca user ma khong con quyen write

            if all_write_user_ids is not None and len(all_write_user_ids) > 0:
                # find current write user ids
                self.env.cr.execute(
                    """select res_user_id from document_permission where model like 'crm' and type like 'write' and res_user_id in %s and res_id=%s """,
                    (tuple(e[0] for e in all_write_user_ids), self.id,))
                current_write_user_ids = self.env.cr.fetchall()
                # tim tat ca cac user vua duoc them quyen write
                new_write_user_ids = []
                for e in all_write_user_ids:
                    if e[0] not in list(a[0] for a in current_write_user_ids):
                        new_write_user_ids.append(e[0])
                for e in new_write_user_ids:
                    self.env['document.permission'].sudo().create({
                        'type': 'write',
                        'model': 'crm',
                        'res_id': self.id,
                        'res_user_id': e,
                    })
                self.env.cr.execute(
                    """delete from document_permission where model like 'crm' and type like 'read' and res_user_id in %s and res_id=%s """,
                    (tuple(e[0] for e in all_write_user_ids), self.id,))
                # xoa tat ca cac user ma co quyen read truoc do
            else:
                self.env['document.permission'].sudo().search(
                    [('model', 'like', 'crm'), ('type', 'like', 'write'), ('res_id', '=', self.id)]).unlink()

            # read permission

            # list all users have permission read
            self.env.cr.execute(
                """select res_user_id from document_crm_part_read_user_rel where crm_part_id = %s""",
                (self.id,))
            all_read_users_ids = self.env.cr.fetchall()

            if all_read_users_ids is not None and len(all_read_users_ids) > 0:
                self.env.cr.execute(
                    """select res_user_id from document_permission where model like 'crm' and type like 'read' and res_user_id in %s""",
                    (tuple(e[0] for e in all_read_users_ids),))
                current_read_user_ids = self.env.cr.fetchall()
                # delete user have not permission read:
                self.env['document.permission'].sudo().search(
                    [('model', 'like', 'crm'), ('type', 'like', 'read'), ('res_id', '=', self.id),
                     ('res_user_id', 'not in', list(str(a[0]) for a in all_write_user_ids)),
                     ('res_user_id', 'not in', list(str(a[0]) for a in all_read_users_ids))]).unlink()
                self.env['document.permission'].sudo().search(
                    [('model', 'like', 'crm'), ('type', 'like', 'read'), ('res_id', '=', self.id),
                     ('res_user_id', 'in', list(str(a[0]) for a in all_write_user_ids))]).unlink()

                for e in all_read_users_ids:
                    if e[0] not in list(a[0] for a in all_write_user_ids) and e[0] not in list(
                            b[0] for b in current_read_user_ids):
                        self.env['document.permission'].sudo().create({
                            'type': 'read',
                            'model': 'crm',
                            'res_id': self.id,
                            'res_user_id': e[0],
                        })
            else:
                self.env['document.permission'].sudo().search(
                    [('model', 'like', 'crm'), ('type', 'like', 'read'), ('res_id', '=', self.id)]).unlink()

        return folder

    def unlink(self):
        google_drive_helper = GoogleDriveHelper()
        for rec in self:
            google_drive_helper.deleteFile(rec.file_id)
            self.env['document.permission'].sudo().search(
                [('model', 'like', 'crm'), ('res_id', '=', rec.id)]).unlink()
            self.env.cr.execute("""select file_id from document_crm_file where res_id = %s""", (rec.id,))
            file_ids = self.env.cr.fetchall()
            if file_ids is not None and len(file_ids) > 0:
                self.env['document.file.permission'].sudo().search(
                    [('file_id', 'in', tuple(e[0] for e in file_ids))]).unlink()
                self.env['document.crm.file'].sudo().search(
                    [('res_id', '=', rec.id)]).unlink()
        return super(DocumentcrmPart, self).unlink()
