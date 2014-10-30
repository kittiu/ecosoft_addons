import wizard
import pooler

view="""<?xml version="1.0"?>
<form string="Make Batch Payment">
    <label string="This will prepare a batch payment to pay the selected payment vouchers."/>
</form>
"""

class wiz_batch_pay(wizard.interface):
    def _confirm(self,cr,uid,data,context):
        print "_confirm"
        pool=pooler.get_pool(cr.dbname)
        all_pv_ids=data["ids"]
        pv_groups={}
        for pv in pool.get("account.voucher").browse(cr,uid,all_pv_ids):
            if pv.type!="payment":
                raise wizard.except_wizard("Error","Wrong voucher type: %s"%pv.name)
            if pv.state in ("paid","posted"):
                raise wizard.except_wizard("Error","Payment voucher is already paid: %s"%pv.name)
            if pv.state!="checked":
                raise wizard.except_wizard("Error","Payment voucher is not approved: %s"%pv.name)
            pv_groups.setdefault(pv.pay_mode_id.id,[]).append(pv)
        bp_ids=[]
        for pay_mode_id,pvs in pv_groups.items():
            vals={
                "pay_mode_id": pay_mode_id,
            }
            bp_id=pool.get("batch.payment").create(cr,uid,vals)
            bp_ids.append(bp_id)
            for pv in pvs:
                pv.write({"batch_pay_id":bp_id})
        return {
            "type": "ir.actions.act_window",
            "res_model": "batch.payment",
            "domain": [("id","in",bp_ids)],
            "view_type": "form",
            "view_mode": "tree,form",
            "name": "Batch Payment",
        }

    states={
        "init": {
            "actions": [],
            "result": {
                "type": "form",
                "arch": view,
                "fields": {},
                "state": [("confirm","Confirm"),("end","Cancel")],
            },
        },
        "confirm": {
            "result": {
                "type": "action",
                "action": _confirm,
                "state": "end",
            }
        }
    }
wiz_batch_pay("batch.pay")
