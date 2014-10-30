import wizard
import pooler
import base64
import csv
import StringIO
import time
import struct


view1="""<?xml version="1.0"?>
<form string="Export Batch Payment To E-Banking">
    <field name="service"/>
</form>
"""

fields1={
    "service": {
        "type": "selection",
        "selection": [("bbl","Bangkok Bank")],
        "string": "E-Banking Service",
        "required": True,
    },
}

view2="""<?xml version="1.0"?>
<form string="Export Batch Payment To E-Banking">
    <field name="file_chk"/>
    <newline/>
    <field name="file_wht"/>
</form>
"""

fields2={
    "file_chk": {
        "type": "binary",
        "string": "Cheque Payment File",
    },
    "file_wht": {
        "type": "binary",
        "string": "Withholding Tax File",
    }
}

def pack_line(*args):
    line=""
    for a,n in args:
        if a==False or a==None:
            a=""
        if type(a)==type(u""):
            a=a.encode("tis-620")
        if type(a)==type(0.5):
            a=int(a*100.0)
        if type(a)==type(1):
            a=str(a)
            a="0"*(n-len(a))+a
        if type(a)==type(""):
            a=a[:n]
            a+=" "*(n-len(a))
        else:
            raise Exception("Invalid type: "+str(a))
        line+=a
    return line+"\n"

class wiz_batch_pay_export(wizard.interface):
    def _init(self,cr,uid,data,context):
        pool=pooler.get_pool(cr.dbname)
        bp_id=data["id"]
        bp=pool.get("batch.payment").browse(cr,uid,bp_id)
        if bp.state=="paid":
            raise wizard.except_wizard("Error","Batch payment is already paid")
        return {}

    def _export(self,cr,uid,data,context):
        print "_import"
        pool=pooler.get_pool(cr.dbname)
        bp_id=data["id"]
        bp=pool.get("batch.payment").browse(cr,uid,bp_id)
        form=data["form"]
        service=form["service"]
        if service=="bbl":
            company_code=bp.pay_mode_id.company_code
            if not company_code:
                raise wizard.except_wizard("Error","Company code is not configured")
            user=pool.get("res.users").browse(cr,uid,uid)
            comp_name=user.company_id.name
            comp_part=user.company_id.partner_id
            if not comp_part.address:
                raise wizard.except_wizard("Error","Missing address for own company")
            comp_addr=comp_part.address[0]
            pay_date=time.strftime("%d%m%Y",time.strptime(bp.date,"%Y-%m-%d"))
            account_no=bp.pay_mode_id.bank_account_id.acc_number or "0000000000"

            # write cheque file
            count=1
            data1=pack_line(("CHQ",3),("1",1),(company_code,8),("99",2),(count,4),(account_no,10),(comp_name,30),(pay_date,8),("",354))
            chk_total=0.0
            for pv in bp.vouchers:
                count+=1
                part=pv.partner_id
                if not part.address:
                    raise wizard.except_wizard("Error","Missing address for partner '%s'"%part.name)
                addr=part.address[0]
                recv_name=part.name
                addr1=addr.street
                addr2=addr.street2
                addr3=addr.city
                zip=addr.zip
                ref1=pv.name
                ref2=count-1
                ref3=[]
                if pv.doc_receipt:
                    ref3.append("OR")
                if pv.doc_invoice:
                    ref3.append("OT")
                if pv.doc_id:
                    ref3.append("ID")
                ref3=",".join(ref3)
                gross_amt="0000000000000"
                disc="0000000"
                chrg="0000000"
                wht="0000000"
                vat="0000000"
                net_amt=pv.pay_total or "0000000000000"
                recv_tin=""
                chk_date=pay_date or "00000000"
                spare="00000000000000000000"
                spare+=spare*3+"00000"
                data1+=pack_line(("CHQ",3),("2",1),(company_code,8),("99",2),(count,4),(recv_name,50),(addr1,40),(addr2,40),(addr3,35),(zip,5),(ref1,20),("",13),(gross_amt,13),(disc,7),(chrg,7),(wht,7),(vat,7),(net_amt,13),(ref2,4),("",16),(ref3,20),(recv_tin,10),(chk_date,8),("00",2),(spare,85))
                chk_total+=pv.pay_total
            num_chk=len(bp.vouchers)
            count+=1
            data1+=pack_line(("CHQ",3),("9",1),(company_code,8),("99",2),(count,4),(num_chk,5),(chk_total,15),("",382))

            # write withholding tax file
            comp_tin=user.company_id.partner_id.tin
            count=1
            data2=""
            for pv in bp.vouchers:
                if pv.taxes != []:
                    if not comp_tin:
                        raise wizard.except_wizard("Error","Missing Company Tax ID.")
                    vol_no=int(pay_date[6]+pay_date[7])+43
                    wht_no=pv.wht_no
                    if not wht_no:
                        raise wizard.except_wizard("Error","Missing WHT No. for %s"%pv.name)
                    part=pv.partner_id
                    if not part.address:
                        raise wizard.except_wizard("Error","Missing address for the partner in '%s'"%pv.name)
                    addr=part.address[0]
                    recv_name=part.name
                    recv_addr1=addr.street
                    recv_addr2=(addr.zip or "")+"/"+(addr.city or "")
                    if not (part.tin or part.pin):
                        raise wizard.except_wizard(("Error"),("Missing Tax ID for the partner in %s"%pv.name))
                    elif part.tin:
                        recv_tin="000"+part.tin
                    else:
                        recv_tin=part.pin
                    payer_name=comp_name
                    payer_addr1=comp_addr.street
                    payer_addr2=(comp_addr.zip or "")+"/"+(comp_addr.city or "")
                    payer_tin=comp_part.tin
                    ref1=pv.name
                    descr=pv.name
                    wht_name={}
                    wht_rate={}
                    wht_date={}
                    wht_base={}
                    wht_amount={}
                    for tax_no in range(5):
                        if tax_no <= len(pv.taxes)-1:
                            wht_name[tax_no]=(pv.taxes[tax_no].name)
                            wht_rate[tax_no]=int(pv.taxes[tax_no].amount*100/pv.taxes[tax_no].base)*100
                            wht_date[tax_no]=pay_date
                            wht_base[tax_no]=pv.taxes[tax_no].base or 0.0
                            wht_amount[tax_no]=pv.taxes[tax_no].amount or 0.0
                        else:
                            wht_name[tax_no]=""
                            wht_rate[tax_no]="0000"
                            wht_date[tax_no]=""
                            wht_base[tax_no]="00000000000"
                            wht_amount[tax_no]="00000000000"
                    amt_base=pv.inv_total or 0.0
                    amt_wht=pv.wht or 0.0
                    data2+=pack_line((vol_no,2),("",13),(wht_no,15),(comp_tin,10),(recv_name,50),(recv_tin,13),(recv_addr1,35),(recv_addr2,35),(count,6),("07",2),(wht_name[0],60),(wht_rate[0],4),(wht_date[0],8),(wht_base[0],11),(wht_amount[0],11),(wht_name[1],60),(wht_rate[1],4),(wht_date[1],8),(wht_base[1],11),(wht_amount[1],11),(wht_name[2],60),(wht_rate[2],4),(wht_date[2],8),(wht_base[2],11),(wht_amount[2],11),(wht_name[3],60),(wht_rate[3],4),(wht_date[3],8),(wht_base[3],11),(wht_amount[3],11),(wht_name[4],60),(wht_rate[4],4),(wht_date[4],8),(wht_base[4],11),(wht_amount[4],11),(amt_base,11),(amt_wht,11),("03",2),("",20),(pay_date,8),("",15),("",2))
                    count+=1

        data1=base64.encodestring(data1)
        data2=base64.encodestring(data2)
        return {"file_chk":data1,"file_wht":data2}

    states={
        "init": {
            "actions": [_init],
            "result": {
                "type": "form",
                "arch": view1,
                "fields": fields1,
                "state": [("export","Continue"),("end","Cancel")],
            },
        },
        "export": {
            "actions": [_export],
            "result": {
                "type": "form",
                "arch": view2,
                "fields": fields2,
                "state": [("end","OK")],
            }
        }
    }
wiz_batch_pay_export("batch.pay.export")
