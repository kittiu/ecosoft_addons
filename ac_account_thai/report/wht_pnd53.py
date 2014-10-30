from report.interface import report_int
from report_tools import pdf_fill,pdf_merge
import pooler
from ac_account_thai.num2word import num2word
import datetime

def fmt_tin(tin):
    return "%s %s%s%s%s %s%s%s%s %s"%(tin[0],tin[1],tin[2],tin[3],tin[4],tin[5],tin[6],tin[7],tin[8],tin[9])

def fmt_addr1(addr):
    s=""
    if addr.street:
        s+=addr.street
    if addr.street2:
        s+=", "+addr.street2
    return s

def fmt_addr2(addr):
    s = ""
    if addr.city:
        s+=addr.city
    if addr.zip:
        s+=addr.zip
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
            #"section3": "X",
            "branch_code":"00000",
            "cb_pnd_attach":"Yes",
            "cb_tredecim":"Yes",
            "cb_ordinary_filling":"Yes",
            "road": addr.street,
            "district": addr.city,
            "province": addr.state_id.name,
            "tel": addr.phone,
        }

        ids=pool.get("account.tax.code").search(cr,uid,[("code","like","PND53_")])
        for tc in pool.get("account.tax.code").browse(cr,uid,ids,{"period_id":period_id}):
            vals[tc.code.replace("PND53_","tax")]=tc.sum_period

        vals.update({
            "tax3": 0.0,
            "tax4": vals["tax2"],
        })
        print vals
        vals.update({
            "%d"%month: "Yes",
            "zipcode":addr.zip,
            "tin":partner.tin and fmt_tin(partner.tin) or "",
            "tax1":lang.format("%.2f",vals["tax1"],grouping=True).replace("."," "),
            "tax2":lang.format("%.2f",vals["tax2"],grouping=True).replace("."," "),
            "tax3":lang.format("%.2f",vals["tax3"],grouping=True).replace("."," "),
            "tax4":lang.format("%.2f",vals["tax4"],grouping=True).replace("."," "),
        })
            
        pdf=pdf_fill("addons/ac_account_thai/report/pdf/wht_pnd53.pdf",vals)

        # fill attachments

        tax_code_id=pool.get("account.tax.code").search(cr,uid,[("code","=","PND53_2")])
        base_code_id=pool.get("account.tax.code").search(cr,uid,[("code","=","PND53_1")])

        # find all lines to show in attachments
        ids=pool.get("account.move.line").search(cr,uid,[("tax_code_id","child_of","PND53_2"),("period_id","=",period_id)],order="date")

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
        ROWS_PER_PAGE=7
        num_pages=(len(rows)+ROWS_PER_PAGE-1)/ROWS_PER_PAGE
        row_no=0
        for j in range(0,len(rows),ROWS_PER_PAGE):
            vals={
                "tin": partner.tin and fmt_tin(partner.tin) or "",
                "branch_code":"00000",
                "page_no": j/ROWS_PER_PAGE+1,
                "page_total": num_pages,
            }
            page_rows=rows[j:j+ROWS_PER_PAGE]

            i=0
            base_page=0.0
            tax_page=0.0
            for row in page_rows:
                i+=1
                supp=row[1]
                lines=row[2]
                row_no+=1
                vals.update({
                    "no%d"%i: str(row_no),
                    "line%d_tin"%i: supp.tin and fmt_tin(supp.tin) or "",
                    "line%d_name"%i: supp.name,
                    "line%d_branch_code"%i:"00000",
                    "line%d_addr1"%i: fmt_addr1(addr),
                    "line%d_addr2"%i: fmt_addr2(addr),
                })
                ii=0
                for ml_tax in lines:
                    ii+=1
                    res=pool.get("account.move.line").search(cr,uid,[("tax_code_id","child_of",base_code_id),("move_id","=",ml_tax.move_id.id)])
                    ml_base=res and pool.get("account.move.line").browse(cr,uid,res[0]) or None
                    vals.update({
                        "line%d_date%d"%(i,ii): fmt_thaidate(ml_tax.date),
                        "line%d_type%d"%(i,ii): ml_tax.name,
                        "line%d_base%d"%(i,ii): ml_base and lang.format("%.2f",ml_base.tax_amount,grouping=True).replace("."," ") or "",
                        "line%d_rate%d"%(i,ii): ml_base and "%.0f%%"%(ml_tax.tax_amount*100.0/ml_base.tax_amount) or "",
                        "line%d_tax%d"%(i,ii): lang.format("%.2f",ml_tax.tax_amount,grouping=True).replace("."," "),
                        "line%d_cond%d"%(i,ii): "1",
                    })
                    base_page+=ml_base and ml_base.tax_amount or 0.0
                    tax_page+=ml_tax.tax_amount
            vals.update({
                "Text42_21": lang.format("%.2f",base_page,grouping=True).replace("."," "),
                "Text43_21": lang.format("%.2f",tax_page,grouping=True).replace("."," "),
            })
            pdf2=pdf_fill("addons/ac_account_thai/report/pdf/wht_pnd53_attach.pdf",vals)
            pdf=pdf_merge(pdf,pdf2)
        return (pdf,"pdf")
report_custom("report.wht.pnd53")
