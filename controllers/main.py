# -*- coding: utf-8 -*-

import base64
import functools
import logging
import os
from tempfile import NamedTemporaryFile

import filetype as ft
from werkzeug.exceptions import Forbidden, abort

from odoo import fields, http, tools
from odoo.http import request
from odoo.modules import get_resource_path

_logger = logging.getLogger(__name__)
IMG_EXT = {"jpg", "jpx", "png", "gif", "tif", "bmp"}
VID_EXT = {"mp4": "video/mp4", "webm": "video/webm"}


class ShareController(http.Controller):
    def _get_link(self, **kwargs):
        link = (
            request.env["ooshare.link"]
            .sudo()
            .search(
                [
                    ("access_token", "=", kwargs["token"]),
                    ("expiration_date", ">=", fields.Date.today()),
                ],
                limit=1,
            )
        )
        if not link:
            abort(404)

        # Build the complete name
        doc = kwargs.get("doc", ".")
        doc_abspath = os.path.abspath(os.path.join(link.doc_abspath, doc))

        # Check we don't try to access a directory outside of the scope of the link
        if len(doc_abspath) < len(link.doc_abspath) or link.doc_abspath not in doc_abspath:
            _logger.warn(
                "Attempt to access folder: %s (from link: %s)", doc_abspath, link.access_token
            )
            abort(403)

        return link, doc, doc_abspath

    @http.route(["/ooshare/browse"], auth="public", type="http")
    def browse(self, **kwargs):
        link, doc, doc_abspath = self._get_link(**kwargs)

        # Download file or display directory content
        if os.path.isfile(doc_abspath):
            # Set a minimum delay between file access to avoid overload
            now = fields.Datetime.now()
            if link.access_date and (now - link.access_date).seconds < link.min_delay:
                raise Forbidden("Too many requests received. Please try again in a few minutes.")
            link._update_access_date(now)
            return http.send_file(doc_abspath, as_attachment=True)

        elif os.path.isdir(doc_abspath):
            values = {
                "doc": doc,
                "gallery": "/ooshare/gallery?token={}&doc={}".format(kwargs["token"], doc),
                "back": {
                    "name": "{}{}".format("..", os.path.sep),
                    "url": "/ooshare/browse?token={}&doc={}".format(
                        kwargs["token"],
                        os.path.join(
                            *(
                                doc_abspath.replace(link.doc_abspath, ".").split(os.path.sep)[:-1]
                                or ["."]
                            )
                        ),
                    ),
                },
                "dirs": sorted(
                    [
                        {
                            "name": "{}{}".format(f.name, os.path.sep),
                            "url": "/ooshare/browse?token={}&doc={}".format(
                                kwargs["token"], os.path.join(doc, f.name)
                            ),
                        }
                        for f in os.scandir(doc_abspath)
                        if f.is_dir()
                    ],
                    key=lambda d: d["name"],
                ),
                "files": sorted(
                    [
                        {
                            "name": f.name,
                            "url": "/ooshare/browse?token={}&doc={}".format(
                                kwargs["token"], os.path.join(doc, f.name)
                            ),
                        }
                        for f in os.scandir(doc_abspath)
                        if f.is_file()
                    ],
                    key=lambda d: d["name"],
                ),
            }
            return request.render("ooshare.browse", values)
        else:
            abort(404)

    @http.route(["/ooshare/gallery"], auth="public", type="http")
    def gallery(self, **kwargs):
        link, doc, doc_abspath = self._get_link(**kwargs)
        if not os.path.isdir(doc_abspath):
            abort(404)

        values = {
            "doc": doc,
            "browse": "/ooshare/browse?token={}&doc={}".format(kwargs["token"], doc),
            "imgs": sorted(
                [
                    {
                        "name": f.name,
                        "url": "/ooshare/img?token={}&doc={}".format(
                            kwargs["token"], os.path.join(doc, f.name)
                        ),
                        "url_thumb": "/ooshare/img?token={}&doc={}&thumb=1".format(
                            kwargs["token"], os.path.join(doc, f.name)
                        ),
                    }
                    for f in os.scandir(doc_abspath)
                    if f.is_file()
                    and ft.guess(os.path.join(doc_abspath, f.name))
                    and ft.guess(os.path.join(doc_abspath, f.name)).extension in IMG_EXT
                ],
                key=lambda d: d["name"],
            ),
            "vids": sorted(
                [
                    {
                        "name": f.name,
                        "url": "/ooshare/vid?token={}&doc={}".format(
                            kwargs["token"], os.path.join(doc, f.name)
                        ),
                        "mime": VID_EXT[os.path.splitext(f.name)[1][1:]],
                    }
                    for f in os.scandir(doc_abspath)
                    if f.is_file() and os.path.splitext(f.name)[1][1:] in VID_EXT
                ],
                key=lambda d: d["name"],
            ),
        }

        res = request.render("ooshare.gallery", values)
        return res

    @http.route(["/ooshare/img"], auth="public", type="http")
    def img(self, **kwargs):
        link, doc, doc_abspath = self._get_link(**kwargs)
        if not ft.guess(doc_abspath) or ft.guess(doc_abspath).extension not in IMG_EXT:
            abort(404)

        if not kwargs.get("thumb"):
            return http.send_file(doc_abspath, mimetype=ft.guess(doc_abspath).mime)

        # Generate thumbnail
        img = base64.b64encode(open(doc_abspath, "rb").read())
        img_new = tools.image_resize_image(img, (128, 128))
        with NamedTemporaryFile(mode="wb") as img_new_tmp:
            img_new_tmp.write(base64.b64decode(img_new))
            img_new_tmp.flush()
            return http.send_file(img_new_tmp.name, mimetype=ft.guess(img_new_tmp.name).mime)

    @http.route(["/ooshare/vid"], auth="public", type="http")
    def vid(self, **kwargs):
        link, doc, doc_abspath = self._get_link(**kwargs)
        vid_ext = os.path.splitext(doc_abspath)[1][1:]
        if vid_ext not in VID_EXT:
            abort(404)
        return http.send_file(doc_abspath, mimetype=VID_EXT[vid_ext])

    @http.route(["/novid.jpg", "/novid-<string:thumb>.jpg"])
    def novid(self, thumb="", **kwargs):
        placeholder = functools.partial(get_resource_path, "ooshare", "static", "src", "img")
        if thumb:
            return http.send_file(placeholder("novid-thumb.jpg"), mimetype="image/jpeg")
        return http.send_file(placeholder("novid.jpg"), mimetype="image/jpeg")
