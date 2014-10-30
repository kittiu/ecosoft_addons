import wizard
import pooler

view="""<?xml version="1.0"?>
<form string="Print Tax Form">
    <field name="period_id"/>
    <newline/>
    <field name="tax_form"/>
</form>
"""

fields={
    "period_id": {
        "type": "many2one",
        "relation": "account.period",
        "string": "Period",
        "required": True,
    },
    "tax_form": {
        "type":"selection",
        "selection":[
        ("vat.pp30","Value Added Tax Return - P.P.30"),
        ("wht.pnd3","Withholding Income Tax Return - P.N.D.3"),
        ("wht.pnd53","Withholding Income Tax Return - P.N.D.53"),
        ],
        "string":"Tax Form",
        "required":True,
    },
}

class wiz_print_tax(wizard.interface):
    def _print(self,cr,uid,data,context):
        form=data["form"]
        report_name=form["tax_form"]
        period_id=form["period_id"]
        return {
            "type": "ir.actions.report.xml",
            "report_name": report_name,
        }

    states={
        "init": {
            "actions": [],
            "result": {
                "type": "form",
                "arch": view,
                "fields": fields,
                "state": [("end","Cancel"),("print","Print")],
            },
        },
        "print": {
            "actions": [],
            "result": {
                "type": "action",
                "action": _print,
                "state": "end",
            }
        }
    }
wiz_print_tax("print.tax")
