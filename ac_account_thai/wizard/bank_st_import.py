import wizard
import pooler
import base64
import csv
import StringIO
import time

view="""<?xml version="1.0"?>
<form string="Import Statement From E-Banking">
    <field name="service"/>
    <newline/>
    <field name="file"/>
</form>
"""

fields={
    "service": {
        "type": "selection",
        "selection": [("kbiz","K-Biznet")],
        "string": "E-Banking Service",
    },
    "file": {
        "type": "binary",
        "string": "File",
    }
}

def parse_date(s):
    t=time.strptime(s,"%d/%m/%Y")
    return time.strftime("%Y-%m-%d",t)

def parse_float(s):
    if not s:
        return 0.0
    return float(s.replace(",",""))

class wiz_bank_st_import(wizard.interface):
    def _import(self,cr,uid,data,context):
        print "_import"
        pool=pooler.get_pool(cr.dbname)
        st_id=data["id"]
        form=data["form"]
        file=form["file"]
        data=base64.decodestring(file)
        try:
            data2=[]
            skip=True
            for line in data.split("\n"):
                if line.startswith("Date,"):
                    skip=False
                if not skip:
                    data2.append(line)
            rd=csv.DictReader(StringIO.StringIO("\n".join(data2)))
            lines=[]
            seq=0
            for line in rd:
                seq+=1
                vals={
                    "sequence": seq,
                    "date": parse_date(line["Date"]),
                    "name": line["Description"],
                    "cheque": line.get("Cheque no.",None),
                    "debit": parse_float(line["Deposit"]),
                    "credit": parse_float(line["Withdrawal"]),
                }
                if not lines:
                    bal_start=parse_float(line["Outstanding Balance"])+vals["credit"]-vals["debit"]
                lines.append((0,0,vals))
            if lines:
                pool.get("ac.bank.statement").write(cr,uid,st_id,{"balance_start": bal_start, "lines": lines})
                return {}
        except Exception,e:
            print "ERROR:",e
            raise wizard.except_wizard("Error","Invalid file format")
        raise wizard.except_wizard("Error","Empty bank statement")

    states={
        "init": {
            "actions": [],
            "result": {
                "type": "form",
                "arch": view,
                "fields": fields,
                "state": [("end","Cancel"),("import","Import")],
            },
        },
        "import": {
            "result": {
                "type": "action",
                "action": _import,
                "state": "end",
            }
        }
    }
wiz_bank_st_import("bank.st.import")
