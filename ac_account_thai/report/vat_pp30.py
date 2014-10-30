from report.interface import report_int
from report_tools import pdf_fill,pdf_merge
import pooler
from report import render
import time

def fmt_thaidate(date):
    dt=datetime.datetime.strptime(date,"%Y-%m-%d")
    return "%2d/%d/%d"%(dt.day,dt.month,dt.year+543) 

def set_satang(vals):
    for key in vals.keys():
        if key.startswith("tax"):
            amt=vals[key]
            vals[key]=int(amt)
            vals[key.replace("tax","st")]=int(amt*100.0)%100

def fmt_tin(tin):
    return "%s %s%s%s%s %s%s%s%s %s"%(tin[0],tin[1],tin[2],tin[3],tin[4],tin[5],tin[6],tin[7],tin[8],tin[9])

def rml2pdf(fname,vals):
    rml=file(fname).read()
    rend=render.rml(rml,vals)
    rend.render()
    return rend.get()

def repeatIn(lst,name):
    return [{name:x} for x in lst]

class report_custom(report_int):
    def create(self,cr,uid,ids,datas,context={}):
        pool=pooler.get_pool(cr.dbname)
        res=pool.get("res.lang").search(cr,uid,[("code","=","th_TH")])
        if not res:
            raise Exception("Thai language not installed")
        lang_id=res[0]
        lang=pool.get("res.lang").browse(cr,uid,lang_id)

        period_id=datas["form"]["period_id"]
        period=pool.get("account.period").browse(cr,uid,period_id)
        fy=period.fiscalyear_id
        user=pool.get("res.users").browse(cr,uid,uid)

        year=int(fy.date_stop[:4])+543
        month=int(period.date_stop[5:7])

        partner=user.company_id.partner_id
        vals={
            "place_name": partner.name,
            "year": year,
            "branch_code":"00000",
            "cb_pnd_attach":"Yes",
            "cb_tredecim":"Yes",
            "cb_ordinary_filling":"Yes",
        }

        addr=partner.address[0]
        vals.update({
            "road": addr.street,
            "district": addr.city,
            "province": addr.state_id.name or "",
            "tel": addr.phone,
        })

        ids=pool.get("account.tax.code").search(cr,uid,[("code","like","PP30_")])
        for tc in pool.get("account.tax.code").browse(cr,uid,ids,{"period_id":period_id}):
            vals[tc.code.replace("PP30_","tax")]=tc.sum_period

        vals.update({
            "tax1": vals["tax4"],
            "tax2": 0.0,
            "tax3": 0.0,
        })
        vals.update({
            "tax8": vals["tax5"]>vals["tax7"] and vals["tax5"]-vals["tax7"] or 0.0,
            "tax9": vals["tax7"]>vals["tax5"] and vals["tax7"]-vals["tax5"] or 0.0,
            "tax10": 0.0,
        })
        vals.update({
            
            "tax11": vals["tax8"],
            "tax12": vals["tax9"],
        })
        set_satang(vals)

        vals.update({
            "head_office": "Yes",
            "ordinary_filing": "Yes",
            "zipcode":addr.zip,
            "%d"%month: "Yes",
            "tin":partner.tin and fmt_tin(partner.tin) or "",
            "tax1":str(vals["tax1"])+" "+"%.2d"%(vals["st1"]),
            "tax2":str(vals["tax2"])+" "+"%.2d"%(vals["st2"]),
            "tax3":str(vals["tax3"])+" "+"%.2d"%(vals["st3"]),
            "tax4":str(vals["tax4"])+" "+"%.2d"%(vals["st4"]),
            "tax5":str(vals["tax5"])+" "+"%.2d"%(vals["st5"]),
            "tax6":str(vals["tax6"])+" "+"%.2d"%(vals["st6"]),
            "tax7":str(vals["tax7"])+" "+"%.2d"%(vals["st7"]),
            "tax8":str(vals["tax8"])+" "+"%.2d"%(vals["st8"]),
            "tax9":str(vals["tax9"])+" "+"%.2d"%(vals["st9"]),
            "tax10":str(vals["tax10"])+" "+"%.2d"%(vals["st10"]),
            "tax11":str(vals["tax11"])+" "+"%.2d"%(vals["st11"]),
            "tax12":str(vals["tax12"])+" "+"%.2d"%(vals["st12"]),
            "pay_more": vals["tax12"] and "Yes" or "No",
        })

        pdf=pdf_fill("addons/ac_account_thai/report/pdf/vat_pp30.pdf",vals)

        # attachments for output vat
        ids=pool.get("account.move.line").search(cr,uid,[("tax_code_id.code","=","PP30_5"),("period_id","=",period_id)])
        item_no=0
        PAGE_SIZE=20
        for p in range(0,len(ids),PAGE_SIZE):
            ids2=ids[p:p+PAGE_SIZE]
            if not ids2:
                break
            vals={
                "year": year,
                "month": month,
                "name": partner.name,
                "tin": partner.tin and partner.tin or "",
                "page_no": p/PAGE_SIZE+1,
                "page_total": (len(ids)+PAGE_SIZE-1)/PAGE_SIZE,
                "date": time.strftime("%d-%m-%Y"),
                "repeatIn": repeatIn,
            }
            lines=[]
            total_base=0.0
            total_tax=0.0
            for ml in pool.get("account.move.line").browse(cr,uid,ids2):
                cust=ml.partner_id
                addr=cust.address[0]
                res=pool.get("account.move.line").search(cr,uid,[("tax_code_id.code","=","PP30_4"),("move_id","=",ml.move_id.id)])
                ml2_id=res[0]
                ml2=pool.get("account.move.line").browse(cr,uid,ml2_id)
                item_no+=1
                lines.append({
                    "item_no": item_no,
                    "invoice": ml.invoice and ml.invoice.number or "N/A",
                    "date": ml.date,
                    "customer": cust.name,
                    "base": lang.format("%.2f",ml2.tax_amount,grouping=True),
                    "tax": lang.format("%.2f",ml.tax_amount,grouping=True),
                })
                total_base+=ml2.tax_amount
                total_tax+=ml.tax_amount
            vals.update({
                "lines": lines,
                "total_base": lang.format("%.2f",total_base,grouping=True),
                "total_tax": lang.format("%.2f",total_tax,grouping=True),
            })
            pdf2=rml2pdf("addons/ac_account_thai/report/rml/output_vat.rml",vals)
            pdf=pdf_merge(pdf,pdf2)

        # attachments for input vat
        ids=pool.get("account.move.line").search(cr,uid,[("tax_code_id.code","=","PP30_7"),("period_id","=",period_id)])
        item_no=0
        PAGE_SIZE=20
        for p in range(0,len(ids),PAGE_SIZE):
            ids2=ids[p:p+PAGE_SIZE]
            if not ids2:
                break
            vals={
                "year": year,
                "month": month,
                "name": partner.name,
                "tin": partner.tin,
                "page_no": p/PAGE_SIZE+1,
                "page_total": (len(ids)+PAGE_SIZE-1)/PAGE_SIZE,
                "date": time.strftime("%Y-%m-%d"),
                "repeatIn": repeatIn,
            }
            lines=[]
            total_base=0.0
            total_tax=0.0
            for ml in pool.get("account.move.line").browse(cr,uid,ids2):
                supp=ml.partner_id
                addr=supp.address[0]
                res=pool.get("account.move.line").search(cr,uid,[("tax_code_id.code","=","PP30_6"),("move_id","=",ml.move_id.id)])
                ml2_id=res[0]
                ml2=pool.get("account.move.line").browse(cr,uid,ml2_id)
                item_no+=1
                lines.append({
                    "item_no": item_no,
                    "invoice": ml.invoice and ml.invoice.number or "N/A",
                    "date": ml.date,
                    "supplier": supp.name,
                    "base": lang.format("%.2f",ml2.tax_amount,grouping=True),
                    "tax": lang.format("%.2f",ml.tax_amount,grouping=True),
                })
                total_base+=ml2.tax_amount
                total_tax+=ml.tax_amount
            vals.update({
                "lines": lines,
                "total_base": lang.format("%.2f",total_base,grouping=True),
                "total_tax": lang.format("%.2f",total_tax,grouping=True),
            })
            pdf2=rml2pdf("addons/ac_account_thai/report/rml/input_vat.rml",vals)
            pdf=pdf_merge(pdf,pdf2)

        return (pdf,"pdf")
report_custom("report.vat.pp30")
