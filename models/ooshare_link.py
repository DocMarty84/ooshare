# -*- coding: utf-8 -*-

import os
import uuid
from datetime import datetime, timedelta

from werkzeug.urls import url_encode

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ShareLink(models.Model):
    _name = "ooshare.link"
    _rec_name = "access_token"
    _order = "expiration_date desc, id desc"
    _description = "Share links"

    def _default_access_token(self):
        return uuid.uuid4().hex

    def _default_expiration_date(self):
        return fields.Date.to_string((datetime.now() + timedelta(days=30)).date())

    doc = fields.Char(string="Folder / File")
    doc_abspath = fields.Char(string="Folder / File Absolute Path", compute="_compute_doc_abs")
    access_token = fields.Char(
        "Security Token",
        index=True,
        default=lambda s: s._default_access_token(),
        help="Access token to access the files",
    )
    expiration_date = fields.Date(
        "Expiration Date",
        index=True,
        default=lambda s: s._default_expiration_date(),
        help="The link will be deactivated after this date.",
    )
    min_delay = fields.Integer(
        "Minimum Delay", default=5, help="Minimum delay in seconds between consecutive accesses."
    )
    access_date = fields.Datetime("Last Access Date")
    expired = fields.Boolean("Expired", compute="_compute_expired")
    url = fields.Char(
        "URL",
        compute="_compute_url",
        help="Send this URL to your contacts so they will download the tracks.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        index=True,
        required=True,
        ondelete="cascade",
        default=lambda self: self.env.user,
    )

    @api.constrains("doc")
    def _check_authorized(self):
        for link in self:
            if not self.env["ooshare.folder"]._authorized(link.doc, link.user_id):
                raise ValidationError(
                    _("You are not authorized to share folder %s. Allowed folders:\n%s")
                    % (
                        link.doc,
                        "\n".join(
                            self.env["ooshare.folder"]
                            .sudo()
                            .search([("user_id", "=", link.user_id.id)])
                            .mapped("abspath")
                        )
                        or _("None"),
                    )
                )

    @api.depends("doc")
    def _compute_doc_abs(self):
        for link in self:
            link.doc_abspath = os.path.abspath(link.doc)

    @api.depends("access_token")
    def _compute_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for link in self:
            params = {"token": link.access_token}
            link.url = "{}/ooshare/browse?{}".format(base_url, url_encode(params))

    def _compute_expired(self):
        for link in self:
            link.expired = bool(link.expiration_date < fields.Date.today())

    def _update_access_date(self, date):
        self.write({"access_date": date})
        self.env.cr.commit()
