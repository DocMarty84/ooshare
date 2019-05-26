# -*- coding: utf-8 -*-
{
    "name": "OOShare",
    "author": "Nicolas Martinelli",
    "category": "Uncategorized",
    "summary": "File sharing module",
    "website": "https://koozic.net/",
    "version": "0.1",
    "description": """
File Sharing
============

        """,
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "security/ooshare_security.xml",
        "views/ooshare_menu_views.xml",
        "views/ooshare_folder_views.xml",
        "views/ooshare_link_views.xml",
        "views/ooshare_templates.xml",
    ],
    "installable": True,
    "license": "Other OSI approved licence",
}
