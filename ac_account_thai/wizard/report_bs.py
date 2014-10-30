import wizard
import pooler
import time
from datetime import datetime

view="""<?xml version="1.0"?>
<form string="Open Balance Sheet">
    <field name="date"/>
    <newline/>
    <field name="company_id"/>
    <newline/>
    <field name="include_draft"/>
</form>
"""

fields={
    "date": {
        "type": "date",
        "string": "Date",
        "required": True,
        "default": lambda *a: time.strftime("%Y-%m-%d"),
    },
    "company_id": {
        "type": "many2one",
        "relation": "res.company",
        "string": "Company",
        "required": True,
    },
    "include_draft": {
        "type": "boolean",
        "string": "Include draft entries",
        "default": lambda *a: True,
    },
}

class wiz_report_bs(wizard.interface):
    def _init(self,cr,uid,data,context):
        pool=pooler.get_pool(cr.dbname)
        user=pool.get("res.users").browse(cr,uid,uid)
        return {
            "company_id": user.company_id.id,
        }

    def _open(self,cr,uid,data,context):
        print "report.bs.open",data
        pool=pooler.get_pool(cr.dbname)
        data_id=pool.get("ir.model.data")._get_id(cr,uid,"ac_account_thai","act_report_bs")
        act_id=pool.get("ir.model.data").read(cr,uid,[data_id],["res_id"])[0]["res_id"]
        act=pool.get("ir.actions.act_window").read(cr,uid,[act_id])[0]
        date=data["form"]["date"]
        year_id=pool.get("account.fiscalyear").find(cr,uid,date)
        year=pool.get("account.fiscalyear").browse(cr,uid,year_id)
        if data["form"]["include_draft"]:
            state=False
        else:
            state="posted"
        context={
            "fiscalyear": year_id,
            "date_from": year.date_start,
            "date_to": date,
            "state": state,
        }
        print "context",context
        act["context"]=str(context)
        return act

    states={
        "init": {
            "actions": [_init],
            "result": {
                "type": "form",
                "arch": view,
                "fields": fields,
                "state": [("end","Cancel"),("open","Open")],
            },
        },
        "open": {
            "actions": [],
            "result": {
                "type": "action",
                "action": _open,
                "state": "end",
            }
        }
    }
wiz_report_bs("report.bs")
