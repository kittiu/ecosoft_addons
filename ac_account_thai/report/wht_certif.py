# -*- encoding: utf-8 -*-
from report.interface import report_int
from report_tools import pdf_fill,pdf_merge
#from pdf_tools import pdf_fill,pdf_merge
import pooler
from ac_account_thai.num2word import num2word_th

def fmt_tin(tin):
    return "%s %s%s%s%s %s%s%s%s %s"%(tin[0],tin[1],tin[2],tin[3],tin[4],tin[5],tin[6],tin[7],tin[8],tin[9])

def fmt_addr(addr):
    s=""
    if addr.street:
        s+=addr.street
    if addr.zip:
        s+=", "+addr.zip
    if addr.state_id:
        s+=" "+addr.state_id.name
    return s

class report_custom(report_int):
    def create(self,cr,uid,ids,datas,context={}):
        print "WHT certificate report"
        pool=pooler.get_pool(cr.dbname)

        res=pool.get("res.lang").search(cr,uid,[("code","=","th_TH")])
        if not res:
            raise Exception("Thai language not installed")
        lang_id=res[0]
        lang=pool.get("res.lang").browse(cr,uid,lang_id)

        user=pool.get("res.users").browse(cr,uid,uid)
        partner=user.company_id.partner_id
        vouch=pool.get("account.voucher").browse(cr,uid,ids[0])
        supp=vouch.partner_id

        year=int(vouch.date[0:4])+543
        month=int(vouch.date[5:7])
        day=int(vouch.date[8:10])

        totals={}
        if vouch.move_id:
            for line in vouch.move_id.line_id:
                if line.tax_code_id:
                    totals[line.tax_code_id.code]=totals.get(line.tax_code_id,0.0)+line.tax_amount
        #print "totals",totals

        vals={
            "name1": partner.name,
            "add1": partner.address and fmt_addr(partner.address[0]) or "",
            "tin1": partner.tin and fmt_tin(partner.tin) or "",
            "id1": partner.pin or "",
            "name2": supp.name,
            "add2": supp.address and fmt_addr(supp.address[0]) or "",
            "tin1_2": supp.tin and fmt_tin(supp.tin) or "",
            "id1_2": supp.pin or "",
            "chk4": supp.pin and "Yes" or "",
            "chk7": supp.tin and "Yes" or "",
            "date_pay": day,
            "month_pay": month,
            "year_pay": year,
        }

        total_base=0.0
        total_tax=0.0

        tax=totals.get("50_PND3_5_TAX",0.0) or totals.get("50_PND53_5_TAX")
        if tax:
            base=totals.get("50_PND3_5_BASE",0.0) or totals.get("50_PND53_5_BASE",0.0)
            vals.update({
                "date13": "%d-%d-%d"%(day,month,year),
                "pay1.12": lang.format("%.2f",base,grouping=True).replace("."," "),
                "tax1.12": lang.format("%.2f",tax,grouping=True).replace("."," "),
            })
            total_base+=base
            total_tax+=tax

        tax=totals.get("50_PND3_6_TAX",0.0) or totals.get("50_PND53_6_TAX")
        if tax:
            base=totals.get("50_PND3_6_BASE",0.0) or totals.get("50_PND53_6_BASE",0.0)
            vals.update({
                "date14": "%d-%d-%d"%(day,month,year),
                "pay1.13": lang.format("%.2f",base,grouping=True).replace("."," "),
                "tax1.13": lang.format("%.2f",tax,grouping=True).replace("."," "),
            })
            total_base+=base
            total_tax+=tax

        vals.update({
            "pay1.14": lang.format("%.2f",total_base,grouping=True).replace("."," "),
            "tax1.14": lang.format("%.2f",total_tax,grouping=True).replace("."," "),
            "total": num2word_th(int(total_tax),"th").decode('utf-8'),
        })

        pdf=pdf_fill("addons/ac_account_thai/report/pdf/wht_certif.pdf",vals)
        return (pdf,"pdf")
report_custom("report.wht.certif")
