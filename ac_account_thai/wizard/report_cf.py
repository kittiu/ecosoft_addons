import wizard
import pooler

view="""<?xml version="1.0"?>
<form string="Open Cash Flow Statement">
    <field name="year_id"/>
    <newline/>
    <field name="period_start_id"/>
    <field name="period_end_id"/>
    <field name="company_id"/>
    <field name="include_draft"/>
</form>
"""

fields={
    "year_id": {
        "type": "many2one",
        "relation": "account.fiscalyear",
        "string": "Fiscal Year",
        "required": True,
    },
    "period_start_id": {
        "type": "many2one",
        "relation": "account.period",
        "string": "Start Period",
    },
    "period_end_id": {
        "type": "many2one",
        "relation": "account.period",
        "string": "End Period",
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

class wiz_report_cf(wizard.interface):
    def _init(self,cr,uid,data,context):
        pool=pooler.get_pool(cr.dbname)
        year_id=pool.get("account.fiscalyear").find(cr,uid,exception=False)
        user=pool.get("res.users").browse(cr,uid,uid)
        company_id=user.company_id.id
        return {
            "year_id": year_id,
            "company_id": company_id,
        }

    def _open(self,cr,uid,data,context):
        print "report.cf.open",data
        pool=pooler.get_pool(cr.dbname)
        data_id=pool.get("ir.model.data")._get_id(cr,uid,"ac_account_thai","act_report_cf")
        act_id=pool.get("ir.model.data").read(cr,uid,[data_id],["res_id"])[0]["res_id"]
        act=pool.get("ir.actions.act_window").read(cr,uid,[act_id])[0]
        year_id=data["form"]["year_id"]
        year=pool.get("account.fiscalyear").browse(cr,uid,year_id)
        if data["form"]["include_draft"]:
            state=False
        else:
            state="posted"
        period_start_id=data["form"]["period_start_id"]
        if period_start_id:
            period=pool.get("account.period").browse(cr,uid,period_start_id)
            date_start=period.date_start
        else:
            date_start=year.date_start
        period_end_id=data["form"]["period_end_id"]
        if period_end_id:
            period=pool.get("account.period").browse(cr,uid,period_end_id)
            date_stop=period.date_stop
        else:
            date_stop=year.date_stop
        print "date_start",date_start
        print "date_stop",date_stop
        period_ids=pool.get("account.period").search(cr,uid,[("fiscalyear_id","=",year_id),("date_start",">=",date_start),("date_stop","<=",date_stop)])
        context={
            "fiscalyear": year_id,
            "periods": period_ids,
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
wiz_report_cf("report.cf")
