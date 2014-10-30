##############################################################################
#
#    Copyright (C) 2009 Almacom (Thailand) Ltd.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    "name" : "Thai accounting module",
    "version" : "0.1",
    "depends" : ["account","stock","purchase","sale","ac_report_font_thai","hr"],
    "author" : "Almacom (Thailand) Ltd.",
    "website" : "http://almacom.co.th/",
    "description": """
This module adapts the default accounting module of OpenERP to be suitable for use in Thailand.
It includes added support for bill issues, vouchers, cheques and withholding tax, petty cash, landed costs, discount, tax included prices, etc.
    """,
    "init_xml" : [
    ],
    "demo_xml" : [
    ],
    "update_xml" : [
        "security/ir.model.access.csv",
        "account_data.xml",
        "account_view.xml",
        "account_report.xml",
        "account_workflow.xml",
    ],
    "installable": True,
}
