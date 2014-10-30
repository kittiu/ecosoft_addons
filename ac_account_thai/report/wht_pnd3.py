# -*- encoding: utf-8 -*-
from report.interface import report_int
from report_tools import pdf_fill,pdf_merge
import pooler
from ac_account_thai.num2word import num2word_th
import datetime

def fmt_tin(tin):
    return "%s %s%s%s%s %s%s%s%s %s"%(tin[0],tin[1],tin[2],tin[3],tin[4],tin[5],tin[6],tin[7],tin[8],tin[9])

def fmt_pin(pin):
    return "%s %s%s%s%s %s%s%s%s%s %s%s %s"%(pin[0],pin[1],pin[2],pin[3],pin[4],pin[5],pin[6],pin[7],pin[8],pin[9],pin[10],pin[11],pin[12])

def set_satang(vals):
    for key in vals.keys():
        if key.startswith("tax"):
            amt=vals[key]
            vals[key]=int(amt)
            vals[key.replace("tax","st")]=int(amt*100.0)%100

def fmt_thaidate(date):
    dt=datetime.datetime.strptime(date,"%Y-%m-%d")
    return "%2d/%d/%d"%(dt.day,dt.month,dt.year+543) 

def fmt_addr(addr):
    s=""
    if addr.street:
        s+=addr.street
    if addr.zip:
        s+=", "+addr.zip
    if addr.state_id:
        s+=" "+addr.state_id.name
    return s

def fmt_thaidate(date):
    dt=datetime.datetime.strptime(date,"%Y-%m-%d")
    return "%2d/%d/%d"%(dt.day,dt.month,dt.year+543) 

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
        addr=partner.address[0]
        vals={
            "name": partner.name,
            "year": year,
            "branch_code":"00000",
            "cb_pnd_attach":"Yes",
            "cb_tredecim":"Yes",
            "cb_ordinary_filling":"Yes",
            "road": addr.street,
            "district": addr.city,
            "province": addr.state_id.name,
            "tel": addr.phone,
            "zipcode":addr.zip,
            "ordinary":"Yes",
            "month%d"%month: "Yes",
            "tin":partner.tin and fmt_tin(partner.tin) or "",
        }

        ids=pool.get("account.tax.code").search(cr,uid,[("code","like","PND3_")])
        for tc in pool.get("account.tax.code").browse(cr,uid,ids,{"period_id":period_id}):
            vals[tc.code.replace("PND3_","tax")]=tc.sum_period

        vals.update({
            "tax3": 0.0,
            "tax4": vals["tax2"],
        })
        #vals["total_wht_letters"]=num2word(int(vals["tax4"])).upper()+" BAHT" #not used

        vals.update({
            "tax1":("%.2f"%vals["tax1"]).replace("."," "),
            "tax2":("%.2f"%vals["tax2"]).replace("."," "),
            "tax3":("%.2f"%vals["tax3"]).replace("."," "),
            "tax4":("%.2f"%vals["tax4"]).replace("."," "),
        })
        pdf=pdf_fill("addons/ac_account_thai/report/pdf/wht_pnd3.pdf",vals)

        ids=pool.get("account.move.line").search(cr,uid,[("tax_code_id.code","=","PND3_2"),("period_id","=",period_id)])
        
        # fill attachments

        tax_code_id=pool.get("account.tax.code").search(cr,uid,[("code","=","PND3_2")])
        base_code_id=pool.get("account.tax.code").search(cr,uid,[("code","=","PND3_1")])

        # find all lines to show in attachments
        ids=pool.get("account.move.line").search(cr,uid,[("tax_code_id","child_of","PND3_2"),("period_id","=",period_id)],order="date")

        # group lines by suppliers
        supp_lines = {}
        for ml in pool.get("account.move.line").browse(cr,uid,ids):
            supp_lines.setdefault(ml.partner_id,[]).append(ml)

        # create list of rows to show in attachments
        rows=[]
        for supp,lines in supp_lines.items():
            for i in range(0,len(lines),3):
                rows.append((lines[i].date,supp,lines[i:i+3]))

        # sort rows by date
        rows=sorted(rows)

        # display rows on pages
        ROWS_PER_PAGE=6
        num_pages=(len(rows)+ROWS_PER_PAGE-1)/ROWS_PER_PAGE

        for j in range(0,len(rows),ROWS_PER_PAGE):
            vals={
                "tin": partner.tin and fmt_tin(partner.tin) or "",
                "branch_code":"00000",
                "page_no": j/ROWS_PER_PAGE+1,
                "page_total": num_pages,
            }
            page_rows=rows[j:j+ROWS_PER_PAGE]

            i=0
            for row in page_rows:
                i+=1
                supp=row[1]
                lines=row[2]

                vals.update({
                    "line%d_tin"%i: supp.tin and fmt_tin(supp.tin) or "",
                    "line%d_pin"%i: supp.pin and fmt_pin(supp.pin) or "",
                    "line%d_name"%i: supp.name.split(" ")[0] or "",
                    "line%d_surname"%i: supp.name.split(" ")[1] if len(supp.name.split(" "))>1 else "", # TODO: add the field in pantner or split the space
                    "line%d_branch_code"%i:"00000",
                    "line%d_addr"%i: fmt_addr(addr) or "",
                })
                ii=0
                for ml_tax in lines:
                    ii+=1
                    res=pool.get("account.move.line").search(cr,uid,[("tax_code_id","child_of",base_code_id),("move_id","=",ml_tax.move_id.id)])
                    ml_base=res and pool.get("account.move.line").browse(cr,uid,res[0]) or None
                    vals.update({
                        "line%d_date%d"%(i,ii): fmt_thaidate(ml_tax.date),
                        "line%d_type%d"%(i,ii): ml_tax.name or "",
                        "line%d_base%d"%(i,ii): ml_base and lang.format("%.2f",ml_base.tax_amount,grouping=True) or "",
                        "line%d_rate%d"%(i,ii): ml_base and "%.0f%%"%(ml_tax.tax_amount*100.0/ml_base.tax_amount) or "",
                        "line%d_tax%d"%(i,ii): lang.format("%.2f",ml_tax.tax_amount,grouping=True) or "",
                        "line%d_cond%d"%(i,ii): "1",
                    })
            pdf2=pdf_fill("addons/ac_account_thai/report/pdf/wht_pnd3_attach.pdf",vals)
            pdf=pdf_merge(pdf,pdf2)
        return (pdf,"pdf")

report_custom("report.wht.pnd3")
