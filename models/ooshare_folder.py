# -*- coding: utf-8 -*-

import os

from odoo import api, fields, models


class ShareFolder(models.Model):
    _name = "ooshare.folder"
    _description = "Share folders"

    user_id = fields.Many2one("res.users", string="User", required=True, ondelete="cascade")
    path = fields.Char(string="Folder Path", required=True)
    abspath = fields.Char(string="Folder Absolute Path", compute="_compute_folder_abs", store=True)

    @api.depends("path")
    def _compute_folder_abs(self):
        for folder in self:
            folder.abspath = os.path.abspath(folder.path) if folder.path else ''

    @api.model
    def _authorized(self, path, user):
        abspath = os.path.abspath(path)
        folders = self.sudo().search([("user_id", "=", user.id)])
        for folder in folders:
            if folder.abspath in abspath:
                return True
        return False
