import wizard
import pooler

view="""<?xml version="1.0"?>
<form string="Replenish Petty Cash">
    <field name="amount"/>
</form>
"""

fields={
    "amount": {
        "type": "float",
        "string": "Requested Amount",
        "required": True,
    },
}

class wiz_pc_reimburse(wizard.interface):
    def _amount(self,cr,uid,data,context):
        print "_amount"
        pool=pooler.get_pool(cr.dbname)
        fund_id=data["id"]
        fund=pool.get("pc.fund").browse(cr,uid,fund_id)
        if fund.balance>=fund.reserved:
            raise wizard.except_wizard("Error","Balance is greater than reserved amount")
        return {"amount": fund.reserved-fund.balance}

    def _make_receipt(self,cr,uid,data,context):
        print "_make_receipt"
        pool=pooler.get_pool(cr.dbname)
        fund_id=data["id"]
        form=data["form"]
        amount=form["amount"]
        vals={
            "fund_id": fund_id,
            "amount": amount,
        }
        recv_id=pool.get("pc.replen").create(cr,uid,vals)

        fund=pool.get("pc.fund").browse(cr,uid,fund_id)
        pay_ids=[pay.id for pay in fund.payments_todo]
        pool.get("pc.payment").write(cr,uid,pay_ids,{"replen_id":recv_id})
        return {
            "type": "ir.actions.act_window",
            "res_model": "pc.replen",
            "domain": [("id","=",recv_id)],
            "view_type": "form",
            "view_mode": "tree,form",
            "name": "New Petty Cash Replenishment",
        }

    states={
        "init": {
            "actions": [_amount],
            "result": {
                "type": "form",
                "arch": view,
                "fields": fields,
                "state": [("end","Cancel"),("make_receipt","Request Replenishment")],
            },
        },
        "make_receipt": {
            "result": {
                "type": "action",
                "action": _make_receipt,
                "state": "end",
            }
        }
    }
wiz_pc_reimburse("pc.reimburse")
