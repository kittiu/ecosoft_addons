##############################################################################
#
#    Copyright (C) 2009 Almacom (Thailand) Ltd.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv,fields
import time
from num2word import num2word
from tools.translate import _
from tools import config
import netsvc
import re

def check_sum_tin(id):
    #TODO:Check sum tin
    if len(id)!=10:
        return False
    return True

def _total_word(self,cr,uid,ids,names,arg,context={}):
    vals={}
    for wd in self.browse(cr,uid,ids):
        vals={
            "total_word": num2word(int(wd.total),"th"),
        }
        vals[wd.id]=vals
    return vals

def check_sum_pin(id):
    if len(id)!=13:
        return False
    mult=13
    sum=0
    for c in id[0:12]:
        try:
            n=int(c)
        except:
            return False
        sum+=n*mult
        mult-=1
    check=(11-sum%11)%10
    if id[12]!=str(check):
        return False
    return True

class res_partner(osv.osv):

    _name="res.partner"
    _inherit="res.partner"
    _columns={
        "tin":fields.char("Taxpayer Identification No.",size=10),
        "pin":fields.char("Personal Identification No.",size=13),
    }

    def _check_pin(self,cr,uid,ids):
        for part in self.browse(cr,uid,ids):
            if part.pin and not check_sum_pin(part.pin):
                return False
        return True

    def _check_tin(self,cr,uid,ids):
        for part in self.browse(cr,uid,ids):
            if part.tin and not check_sum_tin(part.tin):
                return False
        return True

    _constraints = [
        (_check_pin,'Invalid PIN number',['pin']),
        (_check_tin,'Invalid TIN Number',['tin']),
    ]
res_partner()

class product_template(osv.osv):
    _inherit="product.template"
    _columns={
        "cost_method": fields.selection([("standard","Standard Price"),("average","Average Price"),("fifo","FIFO"),("lot","Specific Lot")],"Costing Method",required=True),
    }

    def update_fifo_cost_price(self,cr,uid,product_id,retrieve_qty,uom_id):
        print "update_fifo_cost_price",product_id,retrieve_qty,uom_id
        prod=self.browse(cr,uid,product_id)
        retrieve_qty_=self.pool.get("product.uom")._compute_qty(cr,uid,uom_id,retrieve_qty,prod.uom_id.id)
        move_ids=self.pool.get("stock.move").search(cr,uid,[("product_id","=",product_id),("fifo_open_qty",">",0),("location_dest_id.usage","=","internal")],order="date")
        rem_qty=retrieve_qty_
        amount=0.0
        price_unit=None
        for move in self.pool.get("stock.move").browse(cr,uid,move_ids):
            used_qty=min(rem_qty,move.fifo_open_qty)
            price_unit=move.price_unit
            amount+=used_qty*price_unit
            move.write({"fifo_open_qty": move.fifo_open_qty-used_qty})
            rem_qty-=used_qty
            if not rem_qty>0:
                break
        if price_unit:
            prod.write({"standard_price": price_unit})
        else:
            price_unit=prod.standard_price
        if rem_qty>0:
            amount+=rem_qty*price_unit
        print "result:",amount/retrieve_qty_
        return amount/retrieve_qty_

    def update_lot_cost_price(self,cr,uid,product_id,retrieve_qty,uom_id,lot_id):
        print "update_lot_cost_price",product_id,retrieve_qty,uom_id,lot_id
        prod=self.browse(cr,uid,product_id)
        res=self.pool.get("stock.move").search(cr,uid,[("product_id","=",product_id),("prodlot_id","=",lot_id),("location_dest_id.usage","=","internal")])
        price_unit=None
        if res:
            move_id=res[0]
            move=self.pool.get("stock.move").browse(cr,uid,move_id)
            price_unit=move.price_unit
        if price_unit:
            prod.write({"standard_price": price_unit})
        else:
            price_unit=prod.standard_price
        print "result:",price_unit
        return price_unit
product_template()

class account_tax(osv.osv):
    _inherit="account.tax"
    _columns={
        "is_wht": fields.boolean("Withholding Tax"),
    }
account_tax()

class account_tax_template(osv.osv):
    _inherit="account.tax.template"
    _columns={
        "is_wht": fields.boolean("Withholding Tax"),
    }
account_tax_template()

class account_invoice(osv.osv):
    _inherit="account.invoice"

    def _discount_extra_amount(self, cr, uid, ids, field_name, arg, context):
        res={}
        for inv in self.browse(cr, uid, ids):
            amt=0.0
            for line in inv.invoice_line:
                amt+=line.discount_extra_amount
            res[inv.id]=amt
        return res

    # copy from addons
    # diff: add discount, tax incl
    def _amount_all(self, cr, uid, ids, name, args, context=None):
        res = {}
        for invoice in self.browse(cr,uid,ids, context=context):
            res[invoice.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0
            }
            for line in invoice.invoice_line:
                if invoice.price_type=="tax_included":
                    res[invoice.id]['amount_total'] += line.price_subtotal_extra
                else:
                    res[invoice.id]['amount_untaxed'] += line.price_subtotal_extra
            for line in invoice.tax_line:
                res[invoice.id]['amount_tax'] += line.amount
            if invoice.price_type=="tax_included":
                res[invoice.id]['amount_untaxed'] = res[invoice.id]['amount_total'] - res[invoice.id]['amount_tax']
            else:
                res[invoice.id]['amount_total'] = res[invoice.id]['amount_tax'] + res[invoice.id]['amount_untaxed']
        return res

    # copy from addons
    def _get_invoice_line(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('account.invoice.line').browse(cr, uid, ids, context=context):
            result[line.invoice_id.id] = True
        return result.keys()

    # copy from addons
    def _get_invoice_tax(self, cr, uid, ids, context=None):
        result = {}
        for tax in self.pool.get('account.invoice.tax').browse(cr, uid, ids, context=context):
            result[tax.invoice_id.id] = True
        return result.keys()

    _columns={
        'price_type': fields.selection([('tax_excluded','Tax excluded'),('tax_included','Tax included')],'Price method',required=True,readonly=True,states={'draft':[('readonly',False)]}),
        'discount_extra': fields.char('Additional Discount',size=32,help="Discount : eg. 10% for 10% discount and 10 for fixed discount "),
        'discount_extra_amount': fields.function(_discount_extra_amount, method=True, type="float", string="Additional Disc. Amt."),
        'amount_untaxed': fields.function(_amount_all, method=True, digits=(16, int(config['price_accuracy'])),string='Untaxed',
            store={
                'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line','discount_extra'], 20),
                'account.invoice.tax': (_get_invoice_tax, None, 20),
                'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount'], 20),
            },
            multi='all'),
        'amount_tax': fields.function(_amount_all, method=True, digits=(16, int(config['price_accuracy'])), string='Tax',
            store={
                'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line','discount_extra'], 20),
                'account.invoice.tax': (_get_invoice_tax, None, 20),
                'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount'], 20),
            },
            multi='all'),
        'amount_total': fields.function(_amount_all, method=True, digits=(16, int(config['price_accuracy'])), string='Total',
            store={
                'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line','discount_extra'], 20),
                'account.invoice.tax': (_get_invoice_tax, None, 20),
                'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount'], 20),
            },
            multi='all'),
        }
    _defaults={
        'price_type': lambda *a: 'tax_excluded',
    }

account_invoice()

class account_invoice_line(osv.osv):
    _inherit="account.invoice.line"

    # total discount amount for this line, excluding additional discount
    def _discount_amount(self, cr, uid, ids, field_name, arg,context):
        res={}
        for line in self.browse(cr,uid,ids):
            res[line.id]=compute_discount(line.price_unit*line.quantity,line.discount)
        return res

    # total additional discount amount for this line
    def _discount_extra_amount(self, cr, uid, ids, field_name, arg,context):
        res={}
        for line in self.browse(cr,uid,ids):
            d=line.invoice_id.discount_extra
            if not d:
                res[line.id]=0.0
            elif "%" in d:
                res[line.id]=compute_discount(line.price_unit*line.quantity - line.discount_amount,d)
            else:
                res[line.id]=float(line.invoice_id.discount_extra)/len(line.invoice_id.invoice_line)
        return res

    # diff: total line amount, including line discount and excluding additional discount
    def _amount_line_discount(self, cr, uid, ids, prop, unknow_none,unknow_dict):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            res[line.id] = line.price_unit * line.quantity - line.discount_amount # <<<
        return res

    # diff: total line amount, including line discount and additional discount
    def _amount_line_discount_extra(self, cr, uid, ids, field_name, arg,context):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            res[line.id] = line.price_unit * line.quantity - line.discount_amount - line.discount_extra_amount # <<<
        return res

    # discounted unit price for this line, including additional discount
    def _price_unit_discount(self, cr, uid, ids, field_name, arg,context):
        res = {}
        for line in self.browse(cr, uid, ids):
            if not line.quantity:
                res[line.id]=0.0
            else:
                res[line.id]=line.price_subtotal_extra/line.quantity
        return res

    _columns = {
        'discount': fields.char('Discount',size=32,help="Discount : eg. 10% for 10% discount and 10 for fixed discount "),
        'discount_amount': fields.function(_discount_amount,method=True,string='Discount Amount'),
        'discount_extra_amount': fields.function(_discount_extra_amount,method=True,string='Additional Discount Amount'),
        'price_subtotal': fields.function(_amount_line_discount, method=True, string='Subtotal',store=True, type="float", digits=(16, int(config['price_accuracy']))),
        'price_subtotal_extra': fields.function(_amount_line_discount_extra, method=True, string='Subtotal'),
        'price_unit_discount': fields.function(_price_unit_discount,method=True,string='Discounted Unit Price'),
    }

    # copy from addons r2556
    # diff: use only non-wht
    def product_id_change_unit_price_inv(self, cr, uid, tax_id, price_unit, qty, address_invoice_id, product, partner_id, context=None):
        tax_obj = self.pool.get('account.tax')
        if price_unit:
            taxes = [t for t in tax_obj.browse(cr, uid, tax_id) if not t.is_wht] # <<<
            for tax in tax_obj.compute_inv(cr, uid, taxes, price_unit, qty, address_invoice_id, product, partner_id):
                price_unit = price_unit - tax['amount']
        return {'price_unit': price_unit,'invoice_line_tax_id': tax_id}

    # copy from addons r2556
    # diff: use only non-wht
    def move_line_get(self, cr, uid, invoice_id, context=None):
        res = []
        tax_grouped = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        ait_obj = self.pool.get('account.invoice.tax')
        inv = self.pool.get('account.invoice').browse(cr, uid, invoice_id)
        company_currency = inv.company_id.currency_id.id
        cur = inv.currency_id

        for line in inv.invoice_line:
            mres = self.move_line_get_item(cr, uid, line, context)
            if not mres:
                continue
            res.append(mres)
            tax_code_found= False
            line_taxes=[t for t in line.invoice_line_tax_id if not t.is_wht]
            for tax in tax_obj.compute(cr, uid, line_taxes,
                    (line.price_unit_discount),
                    line.quantity, inv.address_invoice_id.id, line.product_id,
                    inv.partner_id):

                if inv.type in ('out_invoice', 'in_invoice'):
                    tax_code_id = tax['base_code_id']
                    tax_amount = line.price_subtotal * tax['base_sign']
                else:
                    tax_code_id = tax['ref_base_code_id']
                    tax_amount = line.price_subtotal * tax['ref_base_sign']

                if tax_code_found:
                    if not tax_code_id:
                        continue
                    res.append(self.move_line_get_item(cr, uid, line, context))
                    res[-1]['price'] = 0.0
                    res[-1]['account_analytic_id'] = False
                elif not tax_code_id:
                    continue
                tax_code_found = True

                res[-1]['tax_code_id'] = tax_code_id
                res[-1]['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, tax_amount, context={'date': inv.date_invoice})
        return res

    #diff - discounted price
    def move_line_get_item(self, cr, uid, line, context=None):
        return {
            'type':'src',
            'name': line.name[:64],
            'price_unit':line.price_unit_discount,
            'quantity':line.quantity,
            'price':line.price_subtotal_extra,
            'account_id':line.account_id.id,
            'product_id':line.product_id.id,
            'uos_id':line.uos_id.id,
            'account_analytic_id':line.account_analytic_id.id,
            'taxes':line.invoice_line_tax_id,
        }

account_invoice_line()

class account_invoice_tax(osv.osv):
    _inherit="account.invoice.tax"

class account_invoice_tax(osv.osv):
    _inherit = "account.invoice.tax"

    # copy from addons
    # diff: excl wht, add discount, tax incl
    def compute(self, cr, uid, invoice_id, context={}):
        print "invoice.tax compute",invoice_id
        tax_grouped = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        inv = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context)
        cur = inv.currency_id
        company_currency = inv.company_id.currency_id.id

        for line in inv.invoice_line:
            line_taxes=[t for t in line.invoice_line_tax_id if not t.is_wht]
            if inv.price_type=="tax_included":
                tax_vals=tax_obj.compute_inv(cr, uid, line_taxes, line.price_unit_discount, line.quantity, inv.address_invoice_id.id, line.product_id, inv.partner_id)
            else:
                tax_vals=tax_obj.compute(cr, uid, line_taxes, line.price_unit_discount, line.quantity, inv.address_invoice_id.id, line.product_id, inv.partner_id)
            for tax in tax_vals:
                val={}
                val['invoice_id'] = inv.id
                val['name'] = tax['name']
                val['amount'] = tax['amount']
                val['manual'] = False
                val['sequence'] = tax['sequence']
                val['base'] = tax['price_unit'] * line['quantity']

                if inv.type in ('out_invoice','in_invoice'):
                    val['base_code_id'] = tax['base_code_id']
                    val['tax_code_id'] = tax['tax_code_id']
                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['base_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['tax_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_collected_id'] or line.account_id.id
                else:
                    val['base_code_id'] = tax['ref_base_code_id']
                    val['tax_code_id'] = tax['ref_tax_code_id']
                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['ref_base_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['ref_tax_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_paid_id'] or line.account_id.id

                key = (val['tax_code_id'], val['base_code_id'], val['account_id'])
                if not key in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
                    tax_grouped[key]['base_amount'] += val['base_amount']
                    tax_grouped[key]['tax_amount'] += val['tax_amount']

        for t in tax_grouped.values():
            t['amount'] = cur_obj.round(cr, uid, cur, t['amount'])
            t['base_amount'] = cur_obj.round(cr, uid, cur, t['base_amount'])
            t['tax_amount'] = cur_obj.round(cr, uid, cur, t['tax_amount'])
        return tax_grouped
account_invoice_tax()

class account_bill(osv.osv):
    _name="account.bill"

    def _total(self,cr,uid,ids,name,args,context={}):
        vals={}
        for bi in self.browse(cr,uid,ids):
            total=0.0
            for line in bi.lines:
                total+=line.bill_amount
            vals[bi.id]=total
        return vals

    def _report(self,cr,uid,ids,names,arg,context={}):
        all_vals={}
        for bi in self.browse(cr,uid,ids):
            vals={
                #"total_word": num2word(int(bi.total)).upper(),
                "total_word": num2word(int(bi.total),"th"),
            }
            all_vals[bi.id]=vals
        return all_vals

    _columns={
        "type": fields.selection([("receipt","Customer Bill"),("payment","Supplier Bill")],"Type",required=True,readonly=True),
        "name": fields.char("Bill No.",size=64,required=True,readonly=True),
        "partner_id": fields.many2one("res.partner","Partner",required=True),
        "address_invoice_id": fields.many2one("res.partner.address","Invoice Address",required=True),
        "currency_id": fields.many2one("res.currency","Currency",required=True),
        "date": fields.date("Date",required=True),
        "lines": fields.one2many("account.bill.line","bill_id","Bill Lines"),
        "total": fields.function(_total,method=True,type="float",string="Total"),
        "state": fields.selection([("draft","Draft"),("checked","Checked"),("sent","Sent"),("canceled","Canceled")],"Status",required=True,readonly=True),
        "notes": fields.text("Notes"),
        "total_word": fields.function(_total_word,method=True,type="chr",multi="report"),
    }

    _defaults={
        "type": lambda self,cr,uid,context: context.get("type","receipt"),
        'name': lambda self,cr,uid,context: self.pool.get('ir.sequence').get(cr,uid,'bill'),
        "currency_id": lambda self,cr,uid,ctx: self.pool.get("res.users").browse(cr,uid,uid).company_id.currency_id.id,
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "state": lambda *a: "draft",
    }

    def onchange_partner(self,cr,uid,ids,partner_id):
        if not partner_id:
            vals={}
        else:
            res=self.pool.get("res.partner").address_get(cr,uid,[partner_id],["invoice"])
            addr_id=res["invoice"]
            vals={
                "address_invoice_id": addr_id,
            }
        return {"value": vals}

    def button_compute(self,cr,uid,ids,context={}):
        for bi in self.browse(cr,uid,ids):
            partner_id=bi.partner_id.id
            ids=self.pool.get("account.move.line").search(cr,uid,[("partner_id","=",partner_id),("account_id.type","=",bi.type=="receipt" and "receivable" or "payable"),("reconcile_id","=",False)])
            print "ids",ids
            lines=[]
            cr.execute("delete from account_bill_line where bill_id=%d",(bi.id,))
            for ml in self.pool.get("account.move.line").browse(cr,uid,ids):
                print "dates",ml.date_maturity,bi.date
                if not ml.date_maturity or ml.date_maturity<=bi.date:
                    vals={
                        "move_line_inv_id": ml.id,
                        "bill_amount": bi.type=="receipt" and ml.debit-ml.credit or ml.credit-ml.debit,
                        "due_date": ml.date_maturity or ml.date,
                    }
                    if ml.invoice:
                        vals.update({
                            "invoice_id": ml.invoice.id,
                            "inv_amount": ml.invoice.amount_total,
                            "inv_date": ml.invoice.date_invoice,
                        })
                    lines.append((0,0,vals))
            print "lines",lines
            self.write(cr,uid,bi.id,{"lines":lines})
        return True

    def button_checked(self,cr,uid,ids,context={}):
        for bi in self.browse(cr,uid,ids):
            if not bi.lines:
                raise osv.except_osv("Error","Bill is empty!")
        self.write(cr,uid,ids,{"state":"checked"})
        return True

    def button_sent(self,cr,uid,ids,context={}):
        self.write(cr,uid,ids,{"state":"sent"})
        return True

    def button_cancel(self,cr,uid,ids,context={}):
        self.write(cr,uid,ids,{"state":"canceled"})
        return True
account_bill()

class account_bill_line(osv.osv):
    _name="account.bill.line"
    _columns={
        "bill_id": fields.many2one("account.bill","Bill Issue",required=True,ondelete="cascade"),
        "move_line_inv_id": fields.many2one("account.move.line","Invoice Account Entry",required=True),
        "invoice_id": fields.many2one("account.invoice","Invoice"),
        "inv_amount": fields.float("Invoice Amount"),
        "inv_date": fields.date("Invoice Date",required=True),
        "bill_amount": fields.float("Bill Issue Amount",required=True),
        "due_date": fields.date("Due Date",required=True),
    }
account_bill_line()

class payment_mode(osv.osv):
    _name="ac.payment.mode"
    _columns={
        "name": fields.char("Name",size=64,required=True),
        "account_id": fields.many2one("account.account","Account",required=True),
        "journal_id": fields.many2one("account.journal","Journal",required=True),
        "method": fields.selection([("wire","Wire Transfer"),("cheque","Cheque"),("cash","Cash")],"Payment Method",required=True),
        "bank_account_id": fields.many2one("res.partner.bank","Bank Account"),
        "company_code": fields.char("Company Code",size=64),
    }
payment_mode()

class batch_payment(osv.osv):
    _name="batch.payment"

    def _total(self,cr,uid,ids,name,args,context={}):
        vals={}
        for bp in self.browse(cr,uid,ids):
            amt=0.0
            for vouch in bp.vouchers:
                amt+=vouch.pay_total
            vals[bp.id]=amt
        return vals

    _columns={
        "name": fields.char("Name",size=64,required=True,readonly=True),
        "pay_mode_id": fields.many2one("ac.payment.mode","Payment Mode",readonly=True,states={"draft":[("readonly",False)]},select=True,required=True),
        "vouchers": fields.one2many("account.voucher","batch_pay_id","Payment Vouchers",domain=[("type","=","payment")],readonly=True),
        "total": fields.function(_total,method=True,type="float",string="Payment Total"),
        "date": fields.date("Payment Date",required=True,readonly=True,states={"draft":[("readonly",False)]}),
        "state": fields.selection([("draft","Draft"),("ordered","Ordered"),("paid","Paid")],"Status",required=True,readonly=True),
    }
    _defaults={
        "state": lambda *a: "draft",
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        'name': lambda *a: "/",
    }

    def create(self,cr,uid,vals,context={}):
        vals["name"]=self.pool.get("ir.sequence").get(cr,uid,"batch.payment")
        return super(batch_payment,self).create(cr,uid,vals,context)

    def button_ordered(self,cr,uid,ids,context={}):
        print "button_ordered",ids
        for bp in self.browse(cr,uid,ids):
            bp.write({"state":"ordered"})
        return True

    def button_paid(self,cr,uid,ids,context={}):
        print "button_paid",ids
        for bp in self.browse(cr,uid,ids):
            bp.write({"state":"paid"})
            for vouch in bp.vouchers:
                vouch.button_paid()
        return True
batch_payment()

class account_voucher(osv.osv):
    _name="account.voucher"

    def _total(self,cr,uid,ids,name,args,context={}):
        vals={}
        for vouch in self.browse(cr,uid,ids):
            inv_tot=0.0
            wht=0.0
            for line in vouch.lines:
                inv_tot+=line.amount
                for tax in line.taxes:
                    wht+=tax.amount
            vals[vouch.id]={
                "inv_total": inv_tot,
                "wht": wht,
                "pay_total": inv_tot-wht,
            }
        return vals

    _columns={
        "name": fields.char("Voucher No.",size=64,required=True,select=True),
        "type": fields.selection([("receipt","Receipt"),("payment","Payment")],"Type",required=True,readonly=True,select=True),
        "date": fields.date("Date",required=True,readonly=True,states={"draft":[("readonly",False)]},select=True),
        "partner_id": fields.many2one("res.partner","Partner",required=True,readonly=True,states={"draft":[("readonly",False)]},select=True),
        "pay_mode_id": fields.many2one("ac.payment.mode","Payment Mode",readonly=True,states={"draft":[("readonly",False)]},select=True,required=True),
        "currency_id": fields.many2one("res.currency","Currency",required=True,readonly=True,states={"draft":[("readonly",False)]}),
        "cheques": fields.one2many("account.cheque","vouch_id","Cheques"),
        "lines": fields.one2many("account.voucher.line","vouch_id","Voucher Lines",readonly=True,states={"draft":[("readonly",False)]}),
        "state": fields.selection([("draft","Draft"),("checked","Checked"),("paid","Paid"),("posted","Posted"),("canceled","Canceled")],"State",readonly=True,select=True),
        "move_id": fields.many2one("account.move","Journal Entry",readonly=True),
        "notes": fields.text("Additional Information"),
        "draft_by": fields.many2one("res.users","Prepared By",readonly=True),
        "checked_by": fields.many2one("res.users","Checked By",readonly=True),
        "posted_by": fields.many2one("res.users","Posted By",readonly=True),
        "batch_pay_id": fields.many2one("batch.payment","Batch Payment"),
        "bank_account_id": fields.many2one("res.partner.bank","Bank Account"),
        "inv_total": fields.function(_total,method=True,type="float",string="Inv. Total",multi="total"),
        "wht": fields.function(_total,method=True,type="float",string="WHT",multi="total"),
        "pay_total": fields.function(_total,method=True,type="float",string="Pmt. Amount",multi="total"),
        "doc_receipt": fields.boolean("Need Receipt"),
        "doc_invoice": fields.boolean("Need Invoice"),
        "doc_id": fields.boolean("Need ID"),
        "wht_no": fields.char("WHT No.",size=16),
        #"wht_name": fields.char("WHT Name",size=60)
        "taxes": fields.one2many("account.voucher.tax","vouch_id","Taxes"),
    }

    _defaults={
        "name": lambda *a: "/",
        "type": lambda self,cr,uid,context: context.get("type","receipt"),
        "state": lambda *a: "draft",
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "currency_id": lambda self,cr,uid,ctx: self.pool.get("res.users").browse(cr,uid,uid).company_id.currency_id.id,
        "draft_by": lambda self,cr,uid,context: uid,
        "doc_receipt": lambda *a: True,
    }

    def onchange_journal(self,cr,uid,ids,journal_id,type):
        if not journal_id:
            return {}
        jour=self.pool.get("account.journal").browse(cr,uid,journal_id)
        vals={
            "account_id": type=="payment" and jour.default_credit_account_id.id or jour.default_debit_account_id.id,
        }
        return {"value": vals}

    def create(self,cr,uid,vals,context={}):
        vals["name"]=self.pool.get("ir.sequence").get(cr,uid,context.get("type")=="payment" and "payment.voucher" or "receipt.voucher")
        return super(account_voucher,self).create(cr,uid,vals,context)

    def button_checked(self,cr,uid,ids,context={}):
        for vouch in self.browse(cr,uid,ids):
            if not vouch.lines:
                raise osv.except_osv("Error","Missing voucher lines!")
        self.write(cr,uid,ids,{"state":"checked","checked_by":uid})
        return True

    def button_paid(self,cr,uid,ids,context={}):
        self.write(cr,uid,ids,{"state":"paid"})
        return True

    def button_post(self,cr,uid,ids,context={}):
        print "button_post",ids
        for vouch in self.browse(cr,uid,ids):
            # find accounting period
            res=self.pool.get('account.period').search(cr,uid,[('date_start','<=',vouch.date),('date_stop','>=',vouch.date)])
            if res:
                period_id=res[0]
            else:
                raise osv.except_osv("Error","Can not find accounting period!")

            vals={
                "journal_id": vouch.pay_mode_id.journal_id.id,
                "period_id": period_id,
                "date": vouch.date,
            }
            move_id=self.pool.get("account.move").create(cr,uid,vals)
            self.write(cr,uid,vouch.id,{"move_id":move_id})

            # make entry in cash account
            vals={
                "move_id": move_id,
                "account_id": vouch.pay_mode_id.account_id.id,
                "debit": vouch.type=="receipt" and vouch.pay_total or 0.0,
                "credit": vouch.type=="payment" and vouch.pay_total or 0.0,
                "name": vouch.name,
                "partner_id": vouch.partner_id.id,
                "date": vouch.date,
                "vouch_id": vouch.id,
            }
            self.pool.get("account.move.line").create(cr,uid,vals)

            # make entries in payable/receivable account
            to_reconcile=[]
            for line in vouch.lines:
                vals={
                    "move_id": move_id,
                    "account_id": line.account_id.id,
                    "debit": vouch.type=="payment" and line.amount or 0.0,
                    "credit": vouch.type=="receipt" and line.amount or 0.0,
                    "name": line.name,
                    "partner_id": vouch.partner_id.id,
                    "date": vouch.date,
                    "vouch_id": vouch.id,
                }
                ml_id=self.pool.get("account.move.line").create(cr,uid,vals)
                if line.move_line_inv_id:
                    to_reconcile.append([line.move_line_inv_id.id,ml_id])

                # record tax base amounts
                for tax in line.taxes:
                    if not ml_id: # have to create dummy entry to record tax base amount
                        vals={
                            "move_id": move_id,
                            "account_id": line.account_id.id,
                            "debit": 0.0,
                            "credit": 0.0,
                            "name": line.name,
                            "partner_id": vouch.partner_id.id,
                            "date": vouch.date,
                            "vouch_id": vouch.id,
                        }
                        ml_id=self.pool.get("account.move.line").create(cr,uid,vals)
                    vals={
                        "tax_code_id": tax.tax_id.base_code_id.id,
                        "tax_amount": tax.base,
                    }
                    self.pool.get("account.move.line").write(cr,uid,[ml_id],vals)
                    ml_id=None

            # make withholding tax entries
            for tax in vouch.taxes:
                vals={
                    "move_id": move_id,
                    "account_id": tax.account_id.id,
                    "debit": vouch.type=="receipt" and tax.amount or 0.0,
                    "credit": vouch.type=="payment" and tax.amount or 0.0,
                    "name": vouch.name,
                    "tax_code_id": tax.tax_code_id.id,
                    "tax_amount": tax.amount,
                    "partner_id": vouch.partner_id.id,
                    "date": vouch.date,
                    "vouch_id": vouch.id,
                }
                self.pool.get("account.move.line").create(cr,uid,vals)

            self.pool.get("account.move").post(cr,uid,[move_id])
            for ml_ids in to_reconcile:
                self.pool.get("account.move.line").reconcile_partial(cr,uid,ml_ids)
        self.write(cr,uid,ids,{"state":"posted"})
        return True

    def button_cancel(self,cr,uid,ids,context={}):
        for vouch in self.browse(cr,uid,ids):
            if vouch.move_id:
                for line in vouch.lines:
                    ml_inv_id=line.move_line_inv_id
                    if not ml_inv_id:
                        continue
                    if ml_inv_id.reconcile_id:
                        self.pool.get("account.move.reconcile").unlink(cr,uid,[ml_inv_id.reconcile_id.id])
                    elif ml_inv_id.reconcile_partial_id:
                        self.pool.get("account.move.reconcile").unlink(cr,uid,[ml_inv_id.reconcile_partial_id.id])
                if vouch.move_id.state=="posted":
                    self.pool.get("account.move").button_cancel(cr,uid,[vouch.move_id.id])
                self.pool.get("account.move").unlink(cr,uid,[vouch.move_id.id])
        vals={
            "state":"canceled",
            "draft_by":None,
            "checked_by":None,
            "posted_by":None,
        }
        self.write(cr,uid,ids,vals)
        return True

    def button_to_draft(self,cr,uid,ids,context={}):
        self.write(cr,uid,ids,{"state":"draft","draft_by":uid})
        return True

    # compute taxes that apply to voucher
    def button_compute_taxes(self,cr,uid,ids,context={}):
        print "button_compute_taxes",ids
        for vouch in self.browse(cr,uid,ids):
            line_ids=[l.id for l in vouch.lines]
            self.pool.get("account.voucher.line").button_compute_taxes(cr,uid,line_ids)
            cr.execute("delete from account_voucher_tax where vouch_id=%s",(vouch.id,))
            tax_groups={}
            for line in vouch.lines:
                for tax in line.taxes:
                    vals={
                        "tax_id": tax.tax_id.id,
                        "vouch_id": vouch.id,
                        "name": tax.tax_id.name,
                        "account_id": tax.tax_id.account_collected_id.id,
                        "base_code_id": tax.tax_id.base_code_id.id,
                        "tax_code_id": tax.tax_id.tax_code_id.id,
                        "base": tax.base,
                        "amount": tax.amount,
                    }
                    key=(vals['tax_id'],vals["tax_code_id"],vals["base_code_id"],vals["account_id"])
                    if not key in tax_groups:
                        tax_groups[key]=vals
                    else:
                        tax_groups[key]["base"]+=vals["base"]
                        tax_groups[key]["amount"]+=vals["amount"]
            for vals in tax_groups.values():
                self.pool.get("account.voucher.tax").create(cr,uid,vals)
        return True

    #automatic compute tax then save 
    def write(self, cr, uid, ids, vals, context=None):
        #for voucher in self.browse(cr,uid,ids):
            #if vals.get('state',False):
                #if vals.get('state',False)=='draft':
                    #self.button_compute_taxes(cr,uid,ids,context)
            #else:
                #if voucher.state=='draft':
                    #self.button_compute_taxes(cr,uid,ids,context)

        return super(account_voucher, self).write(cr, uid, ids, vals, context=context)

account_voucher()

class account_voucher_line(osv.osv):
    _name="account.voucher.line"
    _columns={
        "vouch_id": fields.many2one("account.voucher","Voucher",required=True,ondelete="cascade"),
        "move_line_inv_id": fields.many2one("account.move.line","Invoice Account Entry"),
        "name": fields.char("Description",size=64,required=True),
        "account_id": fields.many2one("account.account","Account",required=True),
        "amount": fields.float("Invoice Amount",required=True),
        "taxes": fields.one2many("account.voucher.line.tax","vouch_line_id","Taxes"),
    }

    def onchange_move_line(self,cr,uid,ids,ml_id):
        if not ml_id:
            return {}
        ml=self.pool.get("account.move.line").browse(cr,uid,ml_id)
        vals={
            "name": ml.name,
            "account_id": ml.account_id.id,
            "amount": abs(ml.debit-ml.credit),
        }
        return {"value": vals}

    # compute taxes that apply to voucher line from invoice
    def button_compute_taxes(self,cr,uid,ids,context={}):
        print "vl button_compute_taxes",ids
        for line in self.browse(cr,uid,ids):
            #print " count "
            if line.taxes:
                #print "line.taxes" , [i.tax_id.name for i  in line.taxes]
                continue
            ml_inv_id=line.move_line_inv_id
            if not ml_inv_id:
                #print "ml_inv_id" , ml_inv_id
                continue
            inv=ml_inv_id.invoice
            if not inv:
                #print 'inv ' , inv
                continue
            cr.execute("delete from account_voucher_line_tax where vouch_line_id=%s",(line.id,))
            tax_groups={}
            partial=line.amount/inv.amount_total
            #print "partial > ", partial
            for inv_line in inv.invoice_line:
                line_taxes=[t for t in inv_line.invoice_line_tax_id if t.is_wht]
                taxes=self.pool.get("account.tax").compute(cr,uid,line_taxes,inv_line.price_unit_discount ,inv_line.quantity)
                for tax in taxes:
                    vals={
                        "vouch_line_id": line.id,
                        "tax_id": tax["id"],
                        "base": tax["price_unit"]*inv_line.quantity*partial,
                        "amount": tax["amount"]*partial,
                    }
                    key=vals["tax_id"]
                    if not key in tax_groups:
                        tax_groups[key]=vals
                    else:
                        tax_groups[key]["base"]+=vals["base"]
                        tax_groups[key]["amount"]+=vals["amount"]
            for vals in tax_groups.values():
                self.pool.get("account.voucher.line.tax").create(cr,uid,vals)
        return True
account_voucher_line()

class account_voucher_line_tax(osv.osv):
    _name="account.voucher.line.tax"
    _columns={
        "vouch_line_id": fields.many2one("account.voucher.line","Voucher Line",ondelete="cascade",required=True),
        "tax_id": fields.many2one("account.tax","Tax",required=True),
        "base": fields.float("Base",required=True),
        "amount": fields.float("Amount",required=True),
    }
    _defaults={
        "base": lambda self,cr,uid,ctx: ctx.get("amount",0.0),
    }

    def onchange_tax(self,cr,uid,ids,tax_id,base):
        if not tax_id or not base:
            amt=0.0
        else:
            tax=self.pool.get("account.tax").browse(cr,uid,tax_id)
            res=self.pool.get("account.tax").compute(cr,uid,[tax],base,1.0)
            tax_val=res[0]
            amt=tax_val["amount"]
        vals={
            "amount": amt,
        }
        return {"value":vals}
account_voucher_line_tax()

class account_voucher_tax(osv.osv):
    _name="account.voucher.tax"
    _columns={
        "vouch_id": fields.many2one("account.voucher","Voucher",ondelete="cascade",required=True),
        "name": fields.char("Tax Description",size=64,required=True),
        "account_id": fields.many2one("account.account","Account",required=True),
        "base": fields.float("Base",required=True),
        "amount": fields.float("Amount",required=True),
        "base_code_id": fields.many2one("account.tax.code","Base Code"),
        "tax_code_id": fields.many2one("account.tax.code","Tax Code"),
    }
account_voucher_tax()

class account_cheque(osv.osv):
    _name="account.cheque"
    _columns={
        "name": fields.char("Cheque No.",size=64,required=True,readonly=True,states={"hold":[("readonly",False)]},select=2),
        "type": fields.selection([("receipt","Receipt"),("payment","Payment")],"Type",required=True,readonly=True,states={"hold":[("readonly",False)]},select=1),
        "method": fields.selection([("paper","Paper"),("elec","Electronic")],"Method",required=True,readonly=True,states={"hold":[("readonly",False)]},select=1),
        "date": fields.date("Cheque Date",required=True,readonly=True,states={"hold":[("readonly",False)]},select=2),
        "partner_id": fields.many2one("res.partner","Partner",required=True,readonly=True,states={"hold":[("readonly",False)]},select=1),
        "amount": fields.float("Amount",required=True,readonly=True,states={"hold":[("readonly",False)]},select=2),
        "bank_id": fields.many2one("res.bank","Bank",required=True,readonly=True,states={"hold":[("readonly",False)]},select=2),
        "branch": fields.char("Branch",size=64,readonly=True,states={"hold":[("readonly",False)]},select=2),
        "state": fields.selection([("hold","Hold"),("paid","Paid")],"State",readonly=True,required=True,select=1),
        "vouch_id": fields.many2one("account.voucher","Voucher",required=True,readonly=True,states={"hold":[("readonly",False)]},select=2),
    }

    _defaults={
        "type": lambda self,cr,uid,context: context.get("type","payment"),
        "method": lambda *a: "paper",
        "partner_id": lambda self,cr,uid,context: context.get("partner_id",False),
        "state": lambda *a: "hold",
        "date": lambda *a: time.strftime("%Y-%m-%d"),
    }

    def button_paid(self,cr,uid,ids,context={}):
        for chk in self.browse(cr,uid,ids):
            chk.write({"state":"paid"})
        return True

    def onchange_method(self,cr,uid,ids,method):
        vals={
            "name": method=="elec" and "1" or "",
        }
        return {"value": vals}
account_cheque()

# check discount string format
def check_discount_fmt(discount):
    return re.match("\d+(\.\d+)?%?$",discount)!=None

# compute discount amount
def compute_discount(base,discount):
    if not discount:
        return 0.0
    elif "%" in discount:
        return base*float(discount[:-1])/100.0
    else:
        return float(discount)

class purchase_order(osv.osv):
    _inherit="purchase.order"

    def _discount_extra_amount(self, cr, uid, ids, field_name, arg, context):
        res={}
        for order in self.browse(cr, uid, ids):
            amt=0.0
            for line in order.order_line:
                amt+=line.discount_extra_amount
            res[order.id]=amt
        return res

    # copy from addons
    # diff: exclude wht, include discount, support tax incl
    def _amount_all(self, cr, uid, ids, field_name, arg, context):
        print "PO _amount_all"
        res = {}
        cur_obj=self.pool.get('res.currency')
        for order in self.browse(cr, uid, ids):
            res[order.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
            }
            val = val1 = 0.0
            cur=order.pricelist_id.currency_id
            for line in order.order_line:
                line_taxes=[t for t in line.taxes_id if not t.is_wht]
                if order.price_type=="tax_included":
                    tax_vals=self.pool.get('account.tax').compute_inv(cr, uid, line_taxes, line.price_unit_discount, line.product_qty, order.partner_address_id.id, line.product_id, order.partner_id)
                else:
                    tax_vals=self.pool.get('account.tax').compute(cr, uid, line_taxes, line.price_unit_discount, line.product_qty, order.partner_address_id.id, line.product_id, order.partner_id)
                for c in tax_vals:
                    val+= c['amount']
                val1 += line.price_subtotal_extra
            res[order.id]['amount_tax']=cur_obj.round(cr, uid, cur, val)
            if order.price_type=="tax_included":
                res[order.id]['amount_total']=cur_obj.round(cr, uid, cur, val1)
                res[order.id]['amount_untaxed']=res[order.id]['amount_total'] - res[order.id]['amount_tax']
            else:
                res[order.id]['amount_untaxed']=cur_obj.round(cr, uid, cur, val1)
                res[order.id]['amount_total']=res[order.id]['amount_untaxed'] + res[order.id]['amount_tax']
        return res

    def _get_order(self, cr, uid, ids, context={}):
        result = {}
        for line in self.pool.get('purchase.order.line').browse(cr, uid, ids, context=context):
            result[line.order_id.id] = True
        return result.keys()

    _columns={
        'price_type': fields.selection([('tax_excluded','Tax excluded'),('tax_included','Tax included')],'Price method',required=True),
        'discount_extra': fields.char('Additional Discount',size=32,help="Discount : eg. 10% for 10% discount and 10 for fixed discount "),
        'discount_extra_amount': fields.function(_discount_extra_amount, method=True, type="float", string="Additional Disc. Amt."),
        'amount_untaxed': fields.function(_amount_all, method=True, digits=(16, int(config['price_accuracy'])), string='Untaxed Amount',
            store={
                'purchase.order': (lambda self, cr, uid, ids, c={}: ids, ["price_type","discount_extra"], 10),
                'purchase.order.line': (_get_order, ["price_unit","taxes_id","discount","product_qty"], 10),
            }, multi="sums"),
        'amount_tax': fields.function(_amount_all, method=True, digits=(16, int(config['price_accuracy'])), string='Taxes',
            store={
                'purchase.order': (lambda self, cr, uid, ids, c={}: ids, ["price_type","discount_extra"], 10),
                'purchase.order.line': (_get_order, ["price_unit","taxes_id","discount","product_qty"], 10),
            }, multi="sums"),
        'amount_total': fields.function(_amount_all, method=True, digits=(16, int(config['price_accuracy'])), string='Total',
            store={
                'purchase.order': (lambda self, cr, uid, ids, c={}: ids, ["price_type","discount_extra"], 10),
                'purchase.order.line': (_get_order, ["price_unit","taxes_id","discount","product_qty"], 10),
            }, multi="sums"),
    }

    _defaults={
        'price_type': lambda *a: 'tax_excluded',
    }

    def _check_discount(self, cr, uid, ids, context={}):
        for po in self.browse(cr, uid, ids):
            if po.discount_extra and not check_discount_fmt(po.discount_extra):
                return False
        return True

    # add price_unit to reception stock moves
    def action_picking_create(self,cr,uid,ids,*args):
        pick_id=super(purchase_order,self).action_picking_create(cr,uid,ids,*args)
        pick=self.pool.get("stock.picking").browse(cr,uid,pick_id)
        for move in pick.move_lines:
            move.write({"price_unit": move.purchase_line_id.price_unit})
        return pick_id

    # copy from addons
    # diff: add discount
    def inv_line_create(self, cr, uid, a, ol):
        return (0, False, {
            'name': ol.name,
            'account_id': a,
            'price_unit': ol.price_unit or 0.0,
            'quantity': ol.product_qty,
            'discount': ol.discount,
            'product_id': ol.product_id.id or False,
            'uos_id': ol.product_uom.id or False,
            'invoice_line_tax_id': [(6, 0, [x.id for x in ol.taxes_id])],
            'account_analytic_id': ol.account_analytic_id.id,
        })

    # copy from addons
    # diff: add price_type, discount_extra, company
    def action_invoice_create(self, cr, uid, ids, *args):
        res = False
        journal_obj = self.pool.get('account.journal')
        for o in self.browse(cr, uid, ids):
            il = []
            for ol in o.order_line:

                if ol.product_id:
                    a = ol.product_id.product_tmpl_id.property_account_expense.id
                    if not a:
                        a = ol.product_id.categ_id.property_account_expense_categ.id
                    if not a:
                        raise osv.except_osv(_('Error !'), _('There is no expense account defined for this product: "%s" (id:%d)') % (ol.product_id.name, ol.product_id.id,))
                else:
                    a = self.pool.get('ir.property').get(cr, uid, 'property_account_expense_categ', 'product.category')
                fpos = o.fiscal_position or False
                a = self.pool.get('account.fiscal.position').map_account(cr, uid, fpos, a)
                il.append(self.inv_line_create(cr, uid, a, ol))

            a = o.partner_id.property_account_payable.id
            journal_ids = journal_obj.search(cr, uid, [('type', '=','purchase')], limit=1)
            inv = {
                'name': o.partner_ref or o.name,
                'reference': "P%dPO%d" % (o.partner_id.id, o.id),
                'account_id': a,
                'type': 'in_invoice',
                'partner_id': o.partner_id.id,
                'currency_id': o.pricelist_id.currency_id.id,
                'address_invoice_id': o.partner_address_id.id,
                'address_contact_id': o.partner_address_id.id,
                'journal_id': len(journal_ids) and journal_ids[0] or False,
                'origin': o.name,
                'invoice_line': il,
                'fiscal_position': o.partner_id.property_account_position.id,
                'payment_term':o.partner_id.property_payment_term and o.partner_id.property_payment_term.id or False,
                "discount_extra": o.discount_extra,
                "price_type": o.price_type,
            }
            inv_id = self.pool.get('account.invoice').create(cr, uid, inv, {'type':'in_invoice'})
            self.pool.get('account.invoice').button_compute(cr, uid, [inv_id], {'type':'in_invoice'}, set_total=True)

            self.write(cr, uid, [o.id], {'invoice_id': inv_id})
            res = inv_id
        return res
purchase_order()

class purchase_order_line(osv.osv):
    _inherit = "purchase.order.line"

    # total discount amount for this line, excluding additional discount
    def _discount_amount(self, cr, uid, ids, field_name, arg,context):
        res={}
        for line in self.browse(cr,uid,ids):
            res[line.id]=compute_discount(line.price_unit*line.product_qty,line.discount)
        return res

    # total additional discount amount for this line
    def _discount_extra_amount(self, cr, uid, ids, field_name, arg,context):
        res={}
        for line in self.browse(cr,uid,ids):
            d=line.order_id.discount_extra
            if not d:
                res[line.id]=0.0
            elif "%" in d:
                res[line.id]=compute_discount(line.price_subtotal,d)
            else:
                res[line.id]=float(line.order_id.discount_extra)/len(line.order_id.order_line)
        return res

    # diff: total line amount, including line discount and excluding additional discount
    def _amount_line_discount(self, cr, uid, ids, field_name, arg,context):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            cur = line.order_id.pricelist_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur, line.price_unit * line.product_qty - line.discount_amount) # <<<
        return res

    # diff: total line amount, including line discount and additional discount
    def _amount_line_discount_extra(self, cr, uid, ids, field_name, arg,context):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            order=line.order_id
            cur = order.pricelist_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur, line.price_unit * line.product_qty - line.discount_amount - line.discount_extra_amount) # <<<
        return res

    # discounted unit price for this line, including additional discount
    def _price_unit_discount(self, cr, uid, ids, field_name, arg,context):
        res = {}
        for line in self.browse(cr, uid, ids):
            if not line.product_qty:
                res[line.id]=0.0
            else:
                res[line.id]=line.price_subtotal_extra/line.product_qty
        return res

    _columns = {
        'discount': fields.char('Discount',size=32,help="Discount : eg. 10% for 10% discount and 10 for fixed discount "),
        'discount_amount': fields.function(_discount_amount,method=True,string='Discount Amount'),
        'discount_extra_amount': fields.function(_discount_extra_amount,method=True,string='Additional Discount Amount'),
        'price_subtotal': fields.function(_amount_line_discount, method=True, string='Subtotal'),
        'price_subtotal_extra': fields.function(_amount_line_discount_extra, method=True, string='Subtotal'),
        'price_unit_discount': fields.function(_price_unit_discount,method=True,string='Discounted Unit Price'),
    }

    def _check_discount(self, cr, uid, ids, context={}):
        for line in self.browse(cr, uid, ids):
            if line.discount and not check_discount_fmt(line.discount):
                return False
        return True

    _constraints = [
        (_check_discount, _('Wrong discount format'), ['discount']),
    ]
purchase_order_line()

class sale_order(osv.osv):
    _inherit="sale.order"

    def _discount_extra_amount(self, cr, uid, ids, field_name, arg, context):
        res={}
        for order in self.browse(cr, uid, ids):
            amt=0.0
            for line in order.order_line:
                amt+=line.discount_extra_amount
            res[order.id]=amt
        return res

    # diff: exclude wht, include discount, support tax incl
    def _amount_all(self, cr, uid, ids, field_name, arg, context):
        print "SO _amount_all"
        res = {}
        cur_obj=self.pool.get('res.currency')
        for order in self.browse(cr, uid, ids):
            res[order.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
            }
            val = val1 = 0.0
            cur=order.pricelist_id.currency_id
            for line in order.order_line:
                line_taxes=[t for t in line.tax_id if not t.is_wht]
                if order.price_type=="tax_included":
                    tax_vals=self.pool.get('account.tax').compute_inv(cr, uid, line_taxes, line.price_unit_discount, line.product_uom_qty, line.order_id.partner_invoice_id.id, line.product_id, line.order_id.partner_id)
                else:
                    tax_vals=self.pool.get('account.tax').compute(cr, uid, line_taxes, line.price_unit_discount, line.product_uom_qty, line.order_id.partner_invoice_id.id, line.product_id, line.order_id.partner_id)
                for c in tax_vals:
                    val+= c['amount']
                val1 += line.price_subtotal_extra
            res[order.id]['amount_tax']=cur_obj.round(cr, uid, cur, val)
            if order.price_type=="tax_included":
                res[order.id]['amount_total']=cur_obj.round(cr, uid, cur, val1)
                res[order.id]['amount_untaxed']=res[order.id]['amount_total'] - res[order.id]['amount_tax']
            else:
                res[order.id]['amount_untaxed']=cur_obj.round(cr, uid, cur, val1)
                res[order.id]['amount_total']=res[order.id]['amount_untaxed'] + res[order.id]['amount_tax']
        return res

    def _get_order(self, cr, uid, ids, context={}):
        result = {}
        for line in self.pool.get('sale.order.line').browse(cr, uid, ids, context=context):
            result[line.order_id.id] = True
        return result.keys()

    def _amount_line_tax(self, cr, uid, line, context={}):
        val = 0.0
        line_taxes=[t for t in line.tax_id if not t.is_wht] # <<<
        for c in self.pool.get('account.tax').compute(cr, uid, line_taxes, line.price_unit_discount, line.product_uom_qty, line.order_id.partner_invoice_id.id, line.product_id, line.order_id.partner_id):
            val += c['amount']
        return val

    _columns={
        'price_type': fields.selection([('tax_excluded','Tax excluded'),('tax_included','Tax included')],'Price method',required=True),
        'discount_extra': fields.char('Additional Discount',size=32,help="Discount : eg. 10% for 10% discount and 10 for fixed discount "),
        'discount_extra_amount': fields.function(_discount_extra_amount, method=True, type="float", string="Additional Disc. Amt."),
        'amount_untaxed': fields.function(_amount_all, method=True, digits=(16, int(config['price_accuracy'])), string='Untaxed Amount',
            store={
                'sale.order': (lambda self, cr, uid, ids, c={}: ids, ["price_type","discount_extra"], 10),
                'sale.order.line': (_get_order, ["price_unit","tax_id","discount","product_uom_qty"], 10),
            }, multi="sums"),
        'amount_tax': fields.function(_amount_all, method=True, digits=(16, int(config['price_accuracy'])), string='Taxes',
            store={
                'sale.order': (lambda self, cr, uid, ids, c={}: ids, ["price_type","discount_extra"], 10),
                'sale.order.line': (_get_order, ["price_unit","tax_id","discount","product_uom_qty"], 10),
            }, multi="sums"),
        'amount_total': fields.function(_amount_all, method=True, digits=(16, int(config['price_accuracy'])), string='Total',
            store={
                'sale.order': (lambda self, cr, uid, ids, c={}: ids, ["price_type","discount_extra"], 10),
                'sale.order.line': (_get_order, ["price_unit","tax_id","discount","product_uom_qty"], 10),
            }, multi="sums"),
    }
    _defaults={
        'price_type': lambda *a: 'tax_excluded',
    }

    # copy from addons
    # diff: add price_type, discount_extra
    def _make_invoice(self, cr, uid, order, lines, context={}):
        a = order.partner_id.property_account_receivable.id
        if order.payment_term:
            pay_term = order.payment_term.id
        else:
            pay_term = False
        for preinv in order.invoice_ids:
            if preinv.state not in ('cancel',):
                for preline in preinv.invoice_line:
                    inv_line_id = self.pool.get('account.invoice.line').copy(cr, uid, preline.id, {'invoice_id': False, 'price_unit': -preline.price_unit})
                    lines.append(inv_line_id)
        inv = {
            'name': order.client_order_ref or order.name,
            'origin': order.name,
            'type': 'out_invoice',
            'reference': "P%dSO%d" % (order.partner_id.id, order.id),
            'account_id': a,
            'partner_id': order.partner_id.id,
            'address_invoice_id': order.partner_invoice_id.id,
            'address_contact_id': order.partner_order_id.id,
            'invoice_line': [(6, 0, lines)],
            'currency_id': order.pricelist_id.currency_id.id,
            'comment': order.note,
            'payment_term': pay_term,
            'fiscal_position': order.fiscal_position.id or order.partner_id.property_account_position.id,
            "price_type": order.price_type,
            "discount_extra": order.discount_extra,
        }
        inv_obj = self.pool.get('account.invoice')
        inv.update(self._inv_get(cr, uid, order))
        inv_id = inv_obj.create(cr, uid, inv)
        data = inv_obj.onchange_payment_term_date_invoice(cr, uid, [inv_id], pay_term, time.strftime('%Y-%m-%d'))
        if data.get('value', False):
            inv_obj.write(cr, uid, [inv_id], data['value'], context=context)
        inv_obj.button_compute(cr, uid, [inv_id])
        return inv_id
sale_order()

class sale_order_line(osv.osv):
    _inherit="sale.order.line"

    # total discount amount for this line, excluding additional discount
    def _discount_amount(self, cr, uid, ids, field_name, arg,context):
        res={}
        for line in self.browse(cr,uid,ids):
            res[line.id]=compute_discount(line.price_unit*line.product_uom_qty,line.discount)
        return res

    # total additional discount amount for this line
    def _discount_extra_amount(self, cr, uid, ids, field_name, arg,context):
        res={}
        for line in self.browse(cr,uid,ids):
            d=line.order_id.discount_extra
            if not d:
                res[line.id]=0.0
            elif "%" in d:
                res[line.id]=compute_discount(line.price_subtotal,d)
            else:
                res[line.id]=float(line.order_id.discount_extra)/len(line.order_id.order_line)
        return res

    # diff: total line amount, including line discount and excluding additional discount
    def _amount_line_discount(self, cr, uid, ids, field_name, arg,context):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            cur = line.order_id.pricelist_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur, line.price_unit * line.product_uom_qty - line.discount_amount) # <<<
        return res

    # diff: total line amount, including line discount and additional discount
    def _amount_line_discount_extra(self, cr, uid, ids, field_name, arg,context):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            order=line.order_id
            cur = order.pricelist_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur, line.price_unit * line.product_uom_qty - line.discount_amount - line.discount_extra_amount) # <<<
        return res

    # discounted unit price for this line, including additional discount
    def _price_unit_discount(self, cr, uid, ids, field_name, arg,context):
        res = {}
        for line in self.browse(cr, uid, ids):
            if not line.product_uom_qty:
                res[line.id]=0.0
            else:
                res[line.id]=line.price_subtotal_extra/line.product_uom_qty
        return res

    def _get_order(self, cr, uid, ids, context):
        result = {}
        for inv in self.pool.get('sale.order').browse(cr, uid, ids, context=context):
            for line in inv.order_line:
                result[line.id] = True
        return result.keys()

    _columns={
        'discount': fields.char('Discount',size=32,help="Discount : eg. 10% for 10% discount and 10 for fixed discount "),
        'discount_amount': fields.function(_discount_amount,method=True,string='Discount Amount'),
        'discount_extra_amount': fields.function(_discount_extra_amount,method=True,string='Additional Discount Amount'),
        'price_subtotal': fields.function(_amount_line_discount, method=True, string='Subtotal', digits=(16, int(config['price_accuracy']))),
        'price_subtotal_extra': fields.function(_amount_line_discount_extra, method=True, string='Subtotal'),
        'price_unit_discount': fields.function(_price_unit_discount,method=True,string='Discounted Unit Price'),
    }
sale_order_line()

class one2many_dom(fields.one2many):
    def __init__(self, obj, fields_id, string='unknown', limit=None, domain=[], **args):
        fields.one2many.__init__(self,obj,fields_id,string,limit,**args)
        self._domain=domain

    def get(self, cr, obj, ids, name, user=None, offset=0, context=None, values=None):
        if not context:
            context = {}
        if self._context:
            context = context.copy()
        context.update(self._context)
        if not values:
            values = {}
        res = {}
        for id in ids:
            res[id] = []
        ids2 = obj.pool.get(self._obj).search(cr, user, [(self._fields_id, 'in', ids)]+self._domain, limit=self._limit, context=context)
        for r in obj.pool.get(self._obj)._read_flat(cr, user, ids2, [self._fields_id], context=context, load='_classic_write'):
            res[r[self._fields_id]].append(r['id'])
        return res

class pc_fund(osv.osv):
    _name="pc.fund"

    def _balance(self,cr,uid,ids,name,args,context={}):
        print "_balance"
        vals={}
        for fund in self.browse(cr,uid,ids):
            amt=0.0
            for replen in fund.replens:
                if replen.state!='paid':
                    continue
                amt+=replen.amount
                print "replen",replen.amount
            for pay in fund.payments:
                if pay.state!='paid':
                    continue
                amt-=pay.amount_pay
                print "pay",pay.amount_pay
            vals[fund.id]=amt
        return vals

    _columns={
        "name": fields.char("Name",size=64,required=True),
        "account_id": fields.many2one("account.account","Account",required=True),
        "reserved": fields.float("Reserved Amount"),
        "balance": fields.function(_balance,method=True,type="float",string="Current Balance"),
        "payments": fields.one2many("pc.payment","fund_id","Payments"),
        "replens": fields.one2many("pc.replen","fund_id","Replenishments",readonly=True),
        "payments_todo": one2many_dom("pc.payment","fund_id","New Payments",domain=[('replen_id','=',False)],readonly=True),
        "journal_id": fields.many2one("account.journal","Journal",required=True),
        "employee_id": fields.many2one("hr.employee","Employee",required=True),
    }
pc_fund()

class pc_replen(osv.osv):
    _name="pc.replen"

    def _amount_reimb(self,cr,uid,ids,name,args,context={}):
        vals={}
        for recv in self.browse(cr,uid,ids):
            amt=0.0
            for pay in recv.payments:
                amt+=pay.amount_pay
            vals[recv.id]=amt
        return vals

    _columns={
        "fund_id": fields.many2one("pc.fund","Petty Cash Fund",required=True,readonly=True,states={"draft":[("readonly",False)]}),
        "name": fields.char("Name",size=64,required=True,readonly=True),
        "date": fields.date("Date",required=True,readonly=True),
        "invoice_id": fields.many2one("account.invoice","Invoice",readonly=True),
        "payments": fields.one2many("pc.payment","replen_id","Reimbursed Payments",readonly=True),
        "amount": fields.float("Replenish Amount",required=True,readonly=True,states={"draft":[("readonly",False)]}),
        "amount_reimb": fields.function(_amount_reimb,method=True,type="float",string="Reimbursed Amount"),
        "state": fields.selection([("draft","Draft"),("approved","Approved"),("paid","Paid"),("canceled","Canceled")],"Status",readonly=True),
    }
    _defaults={
        "state": lambda *a: "draft",
        'name': lambda self,cr,uid,context: self.pool.get('ir.sequence').get(cr,uid,'pc.replen'),
        "date": lambda *a: time.strftime("%Y-%m-%d"),
    }

    def wkf_approve(self,cr,uid,ids,context={}):
        print "wkf_approve"
        for replen in self.browse(cr,uid,ids):
            lines=[]
            pc_vals={}
            for pay in replen.payments:
                pc_vals={
                    "date_invoice":pay.force_date,
                    "period_id":pay.period_id.id,
                }
                for line in pay.lines:
                    vals={
                        "name": line.name,
                        "account_id": line.account_id.id,
                        "price_unit": line.price_unit,
                        "quantity": line.quantity,
                        "invoice_line_tax_id": [(6,0,[t.id for t in line.taxes])],
                        "product_id": line.product_id.id,
                    }
                    lines.append((0,0,vals))
            if replen.amount>replen.amount_reimb:
                vals={
                    "name": "New petty cash",
                    "account_id": replen.fund_id.account_id.id,
                    "price_unit": replen.amount-replen.amount_reimb,
                    "quantity": 1,
                }
                lines.append((0,0,vals))
            fund=replen.fund_id
            addr=fund.employee_id.address_id
            if not addr:
                raise osv.except_osv(_("Error"),_("Missing address for employee"))
            partner=addr.partner_id
            vals={
                "type": "in_invoice",
                "partner_id": partner.id,
                "address_invoice_id": addr.id,
                "journal_id": fund.journal_id.id,
                "invoice_line": lines,
                "account_id": partner.property_account_payable.id,
                "name": fund.name,
                "origin": replen.name,
            }
            vals.update(pc_vals)
            print "vals",vals
            invoice_id=self.pool.get("account.invoice").create(cr,uid,vals)
            self.pool.get("account.invoice").button_compute(cr,uid,[invoice_id],set_total=True)
            self.pool.get("pc.replen").write(cr,uid,replen.id,{"invoice_id":invoice_id})
        self.write(cr,uid,ids,{"state": "approved"})
        return invoice_id
pc_replen()

class pc_payment(osv.osv):
    _name="pc.payment"

    def _amount(self,cr,uid,ids,name,args,context={}):
        print "_amount"
        vals={}
        for pay in self.browse(cr,uid,ids):
            amt_untaxed=0.0
            amt_tax=0.0
            amt_wht=0.0
            tax_obj = self.pool.get("account.tax")
            for line in pay.lines:
                amt_untaxed+=line.subtotal
                for tax in tax_obj.compute(cr,uid,line.taxes,line.price_unit,line.quantity,product=line.product_id,partner=pay.partner_id):
                    if not tax_obj.browse(cr,uid,tax["id"]).is_wht:
                        amt_tax+=tax["amount"]
                    else:
                        amt_wht+=tax["amount"]

            vals[pay.id]={
                "amount_untaxed": amt_untaxed,
                "amount_tax": amt_tax,
                "amount_total": amt_untaxed+amt_tax,
                "amount_wht": amt_wht,
                "amount_pay": amt_untaxed+amt_tax-amt_wht,
            }
        return vals

    _columns={
        "fund_id": fields.many2one("pc.fund","Petty Cash Fund",required=True,readonly=True,states={"draft":[("readonly",False)]}),
        "name": fields.char("Name",size=64,required=True,readonly=True),
        "partner_id": fields.many2one("res.partner","Supplier",domain=[('supplier','=',True)],required=True,readonly=True,states={"draft":[("readonly",False)]},select=True),
        "lines": fields.one2many("pc.payment.line","pay_id","Lines",readonly=True,states={"draft":[("readonly",False)]}),
        "notes": fields.text("Notes"),
        "replen_id": fields.many2one("pc.replen","Reimbursement",readonly=True),
        "state": fields.selection([("draft","Draft"),("checked","Checked"),("approved","Approved"),("paid","Paid"),("canceled","Canceled")],"Status",readonly=True),
        "date": fields.date("Prepared Date",required=True,readonly=True,select=True),
        "date_paid": fields.date("Paid Date",readonly=True),
        "date_approved": fields.date("Approved Date",readonly=True),
        "date_checked": fields.date("Checked Date",readonly=True),
        "force_date": fields.date("Force Date",help="Select this date substitue the whole date of petty cash operation"),
        "period_id":fields.many2one("account.period","Force Period", domain=[('state','<>','paid')], help="Keep empty to use the period of the validation(invoice) date.", readonly=True, states={'draft':[('readonly',False)]}),
        #"date_received": fields.date("Received Date",readonly=True), #just use paid date for petty cash
        #TODO: all involved employee will use hr.employee insteed of user directly
        "draft_by": fields.many2one("res.users","Prepared By",readonly=True),
        #"received_by": fields.many2one("hr.employee","Received By",required=True), #just keep the employee first
        "checked_by": fields.many2one("res.users","Checked By",readonly=True),
        "approved_by": fields.many2one("res.users","Approved By",readonly=True),
        "amount_untaxed": fields.function(_amount,method=True,type="float",string="Untaxed",multi="amount"),
        "amount_tax": fields.function(_amount,method=True,type="float",string="Tax",multi="amount"),
        "amount_total": fields.function(_amount,method=True,type="float",string="Total",multi="amount"),
        "amount_wht": fields.function(_amount,method=True,type="float",string="Withholding Tax",multi="amount"),
        "amount_pay": fields.function(_amount,method=True,type="float",string="Pay",multi="amount"),
        "employee_id": fields.many2one("hr.employee","Employee",required=True),
    }
    _defaults={
        "state": lambda *a: "draft",
        'name': lambda self,cr,uid,context: self.pool.get('ir.sequence').get(cr,uid,'pc.payment'),
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "draft_by": lambda self,cr,uid,context: uid,
    }
    def _pc_date(self,cr,uid,ids,dates=[]):
        pc = self.browse(cr,uid,ids)
        current_date = time.strftime("%Y-%m-%d")
        vals = {}
        for line in pc:
            for d in dates:
                vals[d]=line.force_date and line.force_date or current_date,
        return vals

    def button_check(self,cr,uid,ids,context={}):
        vals = {"state": "checked","checked_by": uid}
        vals.update(self._pc_date(cr,uid,ids,dates=["date_checked","date"]))
        self.write(cr,uid,ids,vals)
        return True

    def button_approve(self,cr,uid,ids,context={}):
        #just test limitation of user,admin
        approvable=False
        users_roles = self.pool.get('res.users').browse(cr, uid, uid).roles_id
        for role in users_roles:
            if role.name=='Invoice':
                approvable = True
        if approvable or uid==1:#admin uid = 1
            vals = {"state": "approved","approved_by": uid}
            vals.update(self._pc_date(cr,uid,ids,dates=["date_approved"]))
            self.write(cr,uid,ids,vals)
        else:
            raise osv.except_osv(_('Error !'), _('You have no role to approve petty cash payment'))
        return True

    def button_paid(self,cr,uid,ids,context={}):
        vals = {"state": "paid"}
        vals.update(self._pc_date(cr,uid,ids,dates=["date_paid"]))
        self.write(cr,uid,ids,vals)
        return True

    def button_cancel(self,cr,uid,ids,context={}):
        for pay in self.browse(cr,uid,ids):
            if pay.replen_id:
                raise osv.except_osv(_("Error !"),_("Payment is already reimbursed"))
        self.write(cr,uid,ids,{"state": "canceled"})
        return True

    def button_draft(self,cr,uid,ids,context={}):
        self.write(cr,uid,ids,{"state": "draft","draft_by":uid,"date":time.strftime("%Y-%m-%d")})
        return True
pc_payment()

class pc_payment_line(osv.osv):
    _name="pc.payment.line"

    def _subtotal(self,cr,uid,ids,name,args,context={}):
        vals={}
        for line in self.browse(cr,uid,ids):
            vals[line.id]=line.price_unit*line.quantity
        return vals

    _columns={
        "pay_id": fields.many2one("pc.payment","Payment",required=True,ondelete="cascade"),
        "product_id": fields.many2one("product.product","Product"),
        "name": fields.char("Description",size=64,required=True),
        "account_id": fields.many2one("account.account","Account",required=True),
        "price_unit": fields.float("Unit Price",required=True),
        "quantity": fields.float("Quantity",required=True),
        "subtotal": fields.function(_subtotal,method=True,type="float",string="Subtotal"),
        "taxes": fields.many2many("account.tax","pc_payment_tax","line_id","tax_id","Taxes"),
    }

    def onchange_product(self,cr,uid,ids,product_id):
        if not product_id:
            return {}
        prod=self.pool.get("product.product").browse(cr,uid,product_id)
        vals={
            "name": prod.name,
            "account_id": prod.product_tmpl_id.property_account_expense.id or prod.categ_id.property_account_expense_categ.id,
            "price_unit": prod.standard_price,
            "quantity": 1,
            "taxes": [t.id for t in prod.supplier_taxes_id],
        }
        return {"value": vals}
pc_payment_line()

class ac_bank_statement(osv.osv):
    _name="ac.bank.statement"

    def _balance_end(self,cr,uid,ids,name,args,context={}):
        vals={}
        for st in self.browse(cr,uid,ids):
            amt=st.balance_start
            for line in st.lines:
                amt+=line.debit-line.credit
            vals[st.id]=amt
        return vals

    _columns={
        "name": fields.char("Name",size=64,readonly=True),
        "period_id": fields.many2one("account.period","Period",required=True),
        "account_id": fields.many2one("account.account","Account",required=True),
        "balance_start": fields.float("Starting Balance"),
        "balance_end": fields.function(_balance_end,method=True,type="float",string="Ending Balance"),
        "lines": fields.one2many("ac.bank.statement.line","st_id","Lines"),
        "state": fields.selection([("draft","Draft"),("reconciled","Reconciled"),("canceled","Canceled")],"State",readonly=True),
    }
    _defaults={
        "state": lambda *a: "draft",
        "name": lambda self,cr,uid,context: self.pool.get("ir.sequence").get(cr,uid,"ac.bank.statement"),
    }

    def button_reconcile(self,cr,uid,ids,context={}):
        for st in self.browse(cr,uid,ids):
            for line in st.lines:
                if not (line.vouch_id and line.vouch_id.reconciled):
                    raise osv.except_osv("Error","Line %d of bank statement is not reconciled"%line.sequence)
        for ml in st.move_lines:
            if not (ml.vouch_id and ml.vouch_id.reconciled):
                raise osv.except_osv("Error","Accounting transaction %s is not reconciled"%vouch.name)
        self.write(cr,uid,ids,{"state": "reconciled"})
        return True

    def button_cancel(self,cr,uid,ids,context={}):
        self.write(cr,uid,ids,{"state": "canceled"})
        return True

    def button_draft(self,cr,uid,ids,context={}):
        self.write(cr,uid,ids,{"state": "draft"})
        return True
ac_bank_statement()

class ac_bank_reconcile(osv.osv):
    _name="ac.bank.reconcile"

    def _balanced(self,cr,uid,ids,name,args,context={}):
        for rec in self.browse(cr,uid,ids):
            vals={}
            amt1=0.0
            for line in rec.st_lines:
                amt1+=line.debit-line.credit
            amt2=0.0
            for line in rec.move_lines:
                amt2+=line.debit-line.credit
            vals[rec.id]=amt1==amt2
        return vals

    _columns={
        "name": fields.char("Name",size=64),
        "st_lines": fields.one2many("ac.bank.statement.line","bank_reconcile_id","Bank Statement Lines",readonly=True),
        "move_lines": fields.one2many("account.move.line","bank_reconcile_id","Account Entries",readonly=True),
        "balanced": fields.function(_balanced,method=True,type="boolean",string="Balanced"),
    }

    _defaults={
        "name": lambda self,cr,uid,context: self.pool.get("ir.sequence").get(cr,uid,"ac.bank.reconcile"),
    }
ac_bank_reconcile()

class ac_bank_statement_line(osv.osv):
    _name="ac.bank.statement.line"

    def _balance(self,cr,uid,ids,name,args,context={}):
        vals=dict([(id,None) for id in ids])
        start_bals={}
        for line in self.browse(cr,uid,ids):
            if not line.st_id.id in start_bals:
                start_bals[line.st_id.id]=line.st_id.balance_start
        for st_id,start_bal in start_bals.items():
            line_ids=self.search(cr,uid,[("st_id","=",st_id)],order="sequence")
            amt=start_bal
            for line in self.browse(cr,uid,ids):
                amt+=line.debit-line.credit
                if line.id in vals:
                    vals[line.id]=amt
        return vals

    _columns={
        "st_id": fields.many2one("ac.bank.statement","Statement",required=True,ondelete="cascade"),
        "sequence": fields.integer("Sequence",required=True),
        "date": fields.date("Date",required=True),
        "name": fields.char("Description",size=64,required=True),
        "cheque": fields.char("Cheque No.",size=64),
        "debit": fields.float("Deposit"),
        "credit": fields.float("Withdrawal"),
        "balance": fields.function(_balance,method=True,type="float",string="Outstanding Balance"),
        "bank_reconcile_id": fields.many2one("ac.bank.reconcile","Bank Reconciliation"),
        "reconciled": fields.related("bank_reconcile_id","balanced",type="boolean",string="Reconciled"),
        "notes": fields.text("Notes"),
    }
    _order="sequence,id"
ac_bank_statement_line()

class account_move_line(osv.osv):
    _inherit="account.move.line"

    def _latest_bill_line(self,cr,uid,ids,name,args,context={}):
        vals={}
        for ml in self.browse(cr,uid,ids):
            if ml.bill_lines:
                id=ml.bill_lines[-1].id
            else:
                id=False
            vals[ml.id]=id
        return vals

    _columns={
        "bill_lines": fields.one2many("account.bill.line","move_line_inv_id","Bill Issue Lines"),
        "latest_bill_line": fields.function(_latest_bill_line,method=True,type="many2one",relation="account.bill.line",string="Lastest Bill Issue Line"),
        "latest_bill": fields.related("latest_bill_line","bill_id",type="many2one",relation="account.bill",string="Latest Bill"),
        "bank_reconcile_id": fields.many2one("ac.bank.reconcile","Bank Reconciliation"),
        "bank_reconciled": fields.related("bank_reconcile_id","balanced",type="boolean",string="Reconciled"),
        "stock_move_id": fields.many2one("stock.move","Stock Move"),
    }
account_move_line()

class wiz_bank_reconcile(osv.osv_memory):
    _name="wiz.bank.reconcile"
    _columns={
        "st_id": fields.many2one("ac.bank.statement","Bank Statement",readonly=True),
        "account_id": fields.many2one("account.account","Account",readonly=True),
        "st_lines": fields.many2many("ac.bank.statement.line","bank_reconcile_st_lines","recon_id","line_id","Bank Statement Lines"),
        "move_lines": fields.many2many("account.move.line","bank_reconcile_move_lines","recon_id","move_line_id","Account Entries"),
    }

    _defaults={
        "st_id": lambda self,cr,uid,context: context["statement_id"],
        "account_id": lambda self,cr,uid,context: self.pool.get("ac.bank.statement").browse(cr,uid,context["statement_id"]).account_id.id,
    }

    def button_reconcile(self,cr,uid,ids,context={}):
        print "button_reconcile"
        wiz=self.browse(cr,uid,ids[0])
        vals={}
        rec_id=self.pool.get("ac.bank.reconcile").create(cr,uid,vals)
        for st_line in wiz.st_lines:
            self.pool.get("ac.bank.statement.line").write(cr,uid,[st_line.id],{"bank_reconcile_id": rec_id})
        for move_line in wiz.move_lines:
            self.pool.get("account.move.line").write(cr,uid,[move_line.id],{"bank_reconcile_id": rec_id})
        return {
                'view_type': 'form',
                "view_mode": 'tree,form',
                'res_model': 'ac.bank.reconcile',
                'type': 'ir.actions.act_window',
                'domain': [('id','=',rec_id)],
        }

    def button_find_move_line(self,cr,uid,ids,context={}):
        print "button_find_move_line"
        st_id=ids[0]
        st=self.pool.get("ac.bank.statement").browse(cr,uid,st_id)
        wiz=self.browse(cr,uid,ids[0])
        used=set([])
        move_lines=[]
        for st_line in wiz.st_lines:
            dom=[("account_id","=",st.account_id.id),("bank_reconcile_id","=",False)]
            if st_line.debit:
                dom+=[("debit","=",st_line.debit)]
            if st_line.credit:
                dom+=[("credit","=",st_line.credit)]
            if st_line.cheque:
                cheque_ids=self.pool.get("account.cheque").search(cr,uid,[("name","=",st_line.cheque)])
                vouch_ids=[]
                for cheque in self.pool.get("account.cheque").browse(cr,uid,cheque_ids):
                    vouch_ids.append(cheque.vouch_id.id)
                dom+=[("vouch_id","in",vouch_ids)]
            print "dom:",dom
            res=self.pool.get("account.move.line").search(cr,uid,dom)
            found=False
            for ml_id in res:
                if ml_id in used:
                    continue
                move_lines.append(ml_id)
                used.add(ml_id)
                found=True
                break
            if not found:
                raise osv.except_osv("Error","Could not find account entry matching bank statement line %d"%st_line.sequence)
        self.write(cr,uid,[wiz.id],{"move_lines":[(6,0,move_lines)]})
        return True
wiz_bank_reconcile()

class account_journal(osv.osv):
    _inherit="account.journal"
    _columns={
        'type': fields.selection([('sale', 'Sale'), ('purchase', 'Purchase'), ('receipt', 'Receipt'), ('payment','Payment'), ('cash','Cash'), ('general', 'General'), ('situation','Situation')], 'Type', required=True),
    }
account_journal()

class add_cost(osv.osv):
    _name="add.cost"
    _columns={
        "name": fields.char("Doc. No.",size=64,required=True,readonly=True),
        "date": fields.date("Date",required=True),
        "method": fields.selection([("qty","Quantity"),("amount","Amount"),("manual","Manual")],"Allocation Method",required=True),
        "amount": fields.float("Amount",required=True),
        "currency_id": fields.many2one("res.currency","Currency",required=True),
        "desc": fields.char("Description",size=64,required=True),
        "lines": fields.one2many("add.cost.line","cost_id","Items"),
        "move_id": fields.many2one("account.move","Journal Entry",readonly=True),
        "notes": fields.text("Notes"),
        "state": fields.selection([("draft","Draft"),("posted","Posted"),("canceled","Canceled")],"Status",required=True,readonly=True),
        "journal_id": fields.many2one("account.journal","Journal"),
    }
    _defaults={
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "name": lambda self,cr,uid,context: self.pool.get("ir.sequence").get(cr,uid,"add.cost"),
        "state": lambda *a: "draft",
        "currency_id": lambda self,cr,uid,context: self.pool.get('res.users').browse(cr,uid,uid).company_id.currency_id.id,
    }

    def btn_compute(self,cr,uid,ids,context={}):
        for ac in self.browse(cr,uid,ids):
            total_qty=0.0
            total_amount=0.0
            for line in ac.lines:
                total_qty+=line.product_qty
                total_amount+=line.amount
            for line in ac.lines:
                if ac.method=="qty":
                    line.write({"cost":ac.amount*line.product_qty/total_qty})
                elif ac.method=="amount":
                    line.write({"cost":ac.amount*line.amount/total_amount})
                elif ac.method=="manual":
                    pass
        return True

    def btn_post(self,cr,uid,ids,context={}):
        print "btn_post",ids
        self.write(cr,uid,ids,{"state": "posted"})
        for ac in self.browse(cr,uid,ids):
            je_id=None
            for line in ac.lines:
                move=line.move_id
                if move.state!='done':
                    raise osv.except_osv("Error","Stock move not yet completed: %s"%move.product_id.name)
                if not move.price_unit:
                    raise osv.except_osv("Error","Missing unit price in stock move: %s"%move.product_id.name)
                move.write({"price_unit": move.price_unit+line.cost_unit})
                acc_src=move.location_id.account_id.id
                acc_dest=move.location_dest_id.account_id.id
                if acc_src or acc_dest:
                    if not acc_src:
                        acc_src=move.product_id.product_tmpl_id.property_stock_account_input.id
                        if not acc_src:
                            acc_src=move.product_id.categ_id.property_stock_account_input_categ.id
                            if not acc_src:
                                raise osv.except_osv("Error","Missing stock input account: %s"%move.product_id.name)
                    if not acc_dest:
                        acc_dest=move.product_id.product_tmpl_id.property_stock_account_output.id
                        if not acc_dest:
                            acc_dest=move.product_id.categ_id.property_stock_account_output_categ.id
                            if not acc_dest:
                                raise osv.except_osv("Error","Missing stock output account: %s"%move.product_id.name)
                    print "acc_src",acc_src
                    print "acc_dest",acc_dest
                    if not je_id:
                        if not ac.journal_id:
                            raise osv.except_osv("Error","Missing journal")
                        vals={
                            "name": ac.name,
                            "journal_id": ac.journal_id.id,
                        }
                        je_id=self.pool.get("account.move").create(cr,uid,vals)
                        ac.write({"move_id":je_id})
                        print "je_id",je_id
                    vals={
                        "move_id": je_id,
                        "account_id": acc_dest,
                        "debit": line.cost,
                        "credit": 0,
                        "name": ac.name,
                        "product_id": move.product_id.id,
                        "quantity": move.product_qty,
                    }
                    self.pool.get("account.move.line").create(cr,uid,vals)
                    print "xxx"
                    vals={
                        "move_id": je_id,
                        "account_id": acc_src,
                        "credit": line.cost,
                        "debit": 0,
                        "name": ac.name,
                        "product_id": move.product_id.id,
                        "quantity": move.product_qty,
                    }
                    self.pool.get("account.move.line").create(cr,uid,vals)
        return True

    def btn_cancel(self,cr,uid,ids,context={}):
        self.write(cr,uid,ids,{"state": "canceled"})
        return True

    def btn_draft(self,cr,uid,ids,context={}):
        self.write(cr,uid,ids,{"state": "draft"})
        return True
add_cost()

class add_cost_line(osv.osv):
    _name="add.cost.line"

    def _cost_unit(self,cr,uid,ids,name,arg,context={}):
        vals={}
        for ac in self.browse(cr,uid,ids):
            if ac.product_qty:
                vals[ac.id]=ac.cost/ac.product_qty
            else:
                vals[ac.id]=0.0
        return vals

    _columns={
        "cost_id": fields.many2one("add.cost","Landed Costs",required=True,ondelete="cascade"),
        "move_id": fields.many2one("stock.move","Stock Move",required=True),
        "product_id": fields.related("move_id","product_id",type="many2one",relation="product.product",string="Product",readonly=True),
        "product_qty": fields.related("move_id","product_qty",type="float",string="Quantity",readonly=True),
        "date": fields.related("move_id","date",type="date",string="Date",readonly=True),
        "price_unit": fields.related("move_id","price_unit",type="float",string="Unit Price",readonly=True),
        "amount": fields.related("move_id","amount",type="float",string="Amount",readonly=True),
        "state": fields.related("move_id","state",type="selection",selection=[('draft', 'Draft'), ('waiting', 'Waiting'), ('confirmed', 'Confirmed'), ('assigned', 'Available'), ('done', 'Done'), ('cancel', 'Cancelled')],string="Status",readonly=True),
        "cost": fields.float("Allocated Cost",required=True),
        "cost_unit": fields.function(_cost_unit,method=True,type="float",string="Cost Per Unit"),
    }
add_cost_line()

class stock_move(osv.osv):
    _inherit="stock.move"

    def _amount(self,cr,uid,ids,name,arg,context={}):
        vals={}
        for move in self.browse(cr,uid,ids):
            if move.price_unit:
                amt=move.product_qty*move.price_unit
            else:
                amt=False
            vals[move.id]=amt
        return vals

    _columns={
        "amount": fields.function(_amount,method=True,type="float",string="Amount"),
        "move_lines": fields.one2many("account.move.line","stock_move_id","Account Entries"),
        "fifo_open_qty": fields.float("FIFO Open Qty"),
    }

    _order="date desc"

    # copied from default, added fifo/lot costing support
    def action_done(self, cr, uid, ids, context=None):
        print "AT action_done",ids,context
        track_flag = False
        for move in self.browse(cr, uid, ids):
            if move.move_dest_id.id and (move.state != 'done'):
                cr.execute('insert into stock_move_history_ids (parent_id,child_id) values (%s,%s)', (move.id, move.move_dest_id.id))
                if move.move_dest_id.state in ('waiting', 'confirmed'):
                    self.write(cr, uid, [move.move_dest_id.id], {'state': 'assigned'})
                    if move.move_dest_id.picking_id:
                        wf_service = netsvc.LocalService("workflow")
                        wf_service.trg_write(uid, 'stock.picking', move.move_dest_id.picking_id.id, cr)
                    else:
                        pass
                        # self.action_done(cr, uid, [move.move_dest_id.id])
                    if move.move_dest_id.auto_validate:
                        self.action_done(cr, uid, [move.move_dest_id.id], context=context)

            # find unit price if product costing is FIFO and moving from internal location
            if move.product_id.cost_method=="fifo" and move.location_id.usage=="internal": # <<<
                price_unit=self.pool.get("product.template").update_fifo_cost_price(cr,uid,move.product_id.product_tmpl_id.id,move.product_qty,move.product_uom.id)
                move.write({"price_unit":price_unit})
                move=self.browse(cr,uid,move.id)
            # set qty available for FIFO usage
            if move.product_id.cost_method=="fifo" and move.location_dest_id.usage=="internal": # <<<
                move.write({"fifo_open_qty":move.product_qty})
            # find unit price if product costing is LOT and moving from internal location
            if move.product_id.cost_method=="lot" and move.location_id.usage=="internal": # <<<
                price_unit=self.pool.get("product.template").update_lot_cost_price(cr,uid,move.product_id.product_tmpl_id.id,move.product_qty,move.product_uom.id,move.prodlot_id.id)
                move.write({"price_unit":price_unit})
                move=self.browse(cr,uid,move.id)

            #
            # Accounting Entries
            #
            acc_src = None
            acc_dest = None
            if move.location_id.account_id:
                acc_src = move.location_id.account_id.id
            if move.location_dest_id.account_id:
                acc_dest = move.location_dest_id.account_id.id
            if acc_src or acc_dest:
                test = [('product.product', move.product_id.id)]
                if move.product_id.categ_id:
                    test.append( ('product.category', move.product_id.categ_id.id) )
                if not acc_src:
                    acc_src = move.product_id.product_tmpl_id.\
                            property_stock_account_input.id
                    if not acc_src:
                        acc_src = move.product_id.categ_id.\
                                property_stock_account_input_categ.id
                    if not acc_src:
                        raise osv.except_osv(_('Error!'),
                                _('There is no stock input account defined ' \
                                        'for this product: "%s" (id: %d)') % \
                                        (move.product_id.name,
                                            move.product_id.id,))
                if not acc_dest:
                    acc_dest = move.product_id.product_tmpl_id.\
                            property_stock_account_output.id
                    if not acc_dest:
                        acc_dest = move.product_id.categ_id.\
                                property_stock_account_output_categ.id
                    if not acc_dest:
                        raise osv.except_osv(_('Error!'),
                                _('There is no stock output account defined ' \
                                        'for this product: "%s" (id: %d)') % \
                                        (move.product_id.name,
                                            move.product_id.id,))
                if not move.product_id.categ_id.property_stock_journal.id:
                    raise osv.except_osv(_('Error!'),
                        _('There is no journal defined '\
                            'on the product category: "%s" (id: %d)') % \
                            (move.product_id.categ_id.name,
                                move.product_id.categ_id.id,))
                journal_id = move.product_id.categ_id.property_stock_journal.id
                if acc_src != acc_dest:
                    ref = move.picking_id and move.picking_id.name or False
                    product_uom_obj = self.pool.get('product.uom')
                    default_uom = move.product_id.uom_id.id
                    q = product_uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, default_uom)
                    if move.product_id.cost_method in ('average','fifo') and move.price_unit: # <<<
                        amount = q * move.price_unit
                    else:
                        amount = q * move.product_id.standard_price

                    date = time.strftime('%Y-%m-%d')
                    partner_id = False
                    if move.picking_id:
                        partner_id = move.picking_id.address_id and (move.picking_id.address_id.partner_id and move.picking_id.address_id.partner_id.id or False) or False
                    lines = [
                            (0, 0, {
                                'name': move.name,
                                'quantity': move.product_qty,
                                'product_id': move.product_id and move.product_id.id or False,
                                'credit': amount,
                                'account_id': acc_src,
                                'ref': ref,
                                'date': date,
                                'partner_id': partner_id}),
                            (0, 0, {
                                'name': move.name,
                                'product_id': move.product_id and move.product_id.id or False,
                                'quantity': move.product_qty,
                                'debit': amount,
                                'account_id': acc_dest,
                                'ref': ref,
                                'date': date,
                                'partner_id': partner_id})
                    ]
                    self.pool.get('account.move').create(cr, uid, {
                        'name': move.name,
                        'journal_id': journal_id,
                        'line_id': lines,
                        'ref': ref,
                    })
        self.write(cr, uid, ids, {'state': 'done', 'date_planned': time.strftime('%Y-%m-%d %H:%M:%S')})
        wf_service = netsvc.LocalService("workflow")
        for id in ids:
            wf_service.trg_trigger(uid, 'stock.move', id, cr)
        return True
stock_move()

class stock_picking(osv.osv):
    _inherit = 'stock.picking'

    def _get_discount_invoice(self, cursor, user, move_line):
        if move_line.purchase_line_id:
            return move_line.purchase_line_id.discount
        # SO line already returns discount...
        return super(stock_picking, self)._get_discount_invoice(cursor, user,
                move_line)

    def _get_price_type(self,cr,uid,pick):
        if pick.purchase_id:
            return pick.purchase_id.price_type
        elif pick.sale_id:
            return pick.sale_id.price_type
        else:
            return "tax_excluded"

    def _get_discount_extra(self,cr,uid,pick):
        if pick.purchase_id:
            return pick.purchase_id.discount_extra
        elif pick.sale_id:
            return pick.sale_id.discount_extra
        else:
            return False

    # copied from addons, added price_type, discount_extra
    def action_invoice_create(self, cursor, user, ids, journal_id=False,
            group=False, type='out_invoice', context=None):
        '''Return ids of created invoices for the pickings'''
        invoice_obj = self.pool.get('account.invoice')
        invoice_line_obj = self.pool.get('account.invoice.line')
        invoices_group = {}
        res = {}

        for picking in self.browse(cursor, user, ids, context=context):
            if picking.invoice_state != '2binvoiced':
                continue
            payment_term_id = False
            partner = picking.address_id and picking.address_id.partner_id
            if not partner:
                raise osv.except_osv(_('Error, no partner !'),
                    _('Please put a partner on the picking list if you want to generate invoice.'))

            if type in ('out_invoice', 'out_refund'):
                account_id = partner.property_account_receivable.id
                payment_term_id = self._get_payment_term(cursor, user, picking)
            else:
                account_id = partner.property_account_payable.id
            price_type=self._get_price_type(cursor,user,picking)
            discount_extra=self._get_discount_extra(cursor,user,picking)

            address_contact_id, address_invoice_id = \
                    self._get_address_invoice(cursor, user, picking).values()

            comment = self._get_comment_invoice(cursor, user, picking)
            if group and partner.id in invoices_group:
                invoice_id = invoices_group[partner.id]
                invoice = invoice_obj.browse(cursor, user, invoice_id)
                invoice_vals = {
                    'name': (invoice.name or '') + ', ' + (picking.name or ''),
                    'origin': (invoice.origin or '') + ', ' + (picking.name or '') + (picking.origin and (':' + picking.origin) or ''),
                    'comment': (comment and (invoice.comment and invoice.comment+"\n"+comment or comment)) or (invoice.comment and invoice.comment or ''),
                }
                invoice_obj.write(cursor, user, [invoice_id], invoice_vals, context=context)
            else:
                invoice_vals = {
                    'name': picking.name,
                    'origin': (picking.name or '') + (picking.origin and (':' + picking.origin) or ''),
                    'type': type,
                    'account_id': account_id,
                    'partner_id': partner.id,
                    'address_invoice_id': address_invoice_id,
                    'address_contact_id': address_contact_id,
                    'comment': comment,
                    'payment_term': payment_term_id,
                    'fiscal_position': partner.property_account_position.id,
                    "price_type": price_type,
                    "discount_extra": discount_extra,
                    }
                cur_id = self.get_currency_id(cursor, user, picking)
                if cur_id:
                    invoice_vals['currency_id'] = cur_id
                if journal_id:
                    invoice_vals['journal_id'] = journal_id
                invoice_id = invoice_obj.create(cursor, user, invoice_vals,
                        context=context)
                invoices_group[partner.id] = invoice_id
            res[picking.id] = invoice_id
            for move_line in picking.move_lines:
                origin = move_line.picking_id.name
                if move_line.picking_id.origin:
                    origin += ':' + move_line.picking_id.origin
                if group:
                    name = (picking.name or '') + '-' + move_line.name
                else:
                    name = move_line.name

                if type in ('out_invoice', 'out_refund'):
                    account_id = move_line.product_id.product_tmpl_id.\
                            property_account_income.id
                    if not account_id:
                        account_id = move_line.product_id.categ_id.\
                                property_account_income_categ.id
                else:
                    account_id = move_line.product_id.product_tmpl_id.\
                            property_account_expense.id
                    if not account_id:
                        account_id = move_line.product_id.categ_id.\
                                property_account_expense_categ.id

                price_unit = self._get_price_unit_invoice(cursor, user,
                        move_line, type)
                discount = self._get_discount_invoice(cursor, user, move_line)
                tax_ids = self._get_taxes_invoice(cursor, user, move_line, type)
                account_analytic_id = self._get_account_analytic_invoice(cursor,
                        user, picking, move_line)

                #set UoS if it's a sale and the picking doesn't have one
                uos_id = move_line.product_uos and move_line.product_uos.id or False
                if not uos_id and type in ('out_invoice', 'out_refund'):
                    uos_id = move_line.product_uom.id

                account_id = self.pool.get('account.fiscal.position').map_account(cursor, user, partner.property_account_position, account_id)
                invoice_line_id = invoice_line_obj.create(cursor, user, {
                    'name': name,
                    'origin': origin,
                    'invoice_id': invoice_id,
                    'uos_id': uos_id,
                    'product_id': move_line.product_id.id,
                    'account_id': account_id,
                    'price_unit': price_unit,
                    'discount': discount,
                    'quantity': move_line.product_uos_qty or move_line.product_qty,
                    'invoice_line_tax_id': [(6, 0, tax_ids)],
                    'account_analytic_id': account_analytic_id,
                    }, context=context)
                self._invoice_line_hook(cursor, user, move_line, invoice_line_id)

            invoice_obj.button_compute(cursor, user, [invoice_id], context=context,
                    set_total=(type in ('in_invoice', 'in_refund')))
            self.write(cursor, user, [picking.id], {
                'invoice_state': 'invoiced',
                }, context=context)
            self._invoice_hook(cursor, user, picking, invoice_id)
        self.write(cursor, user, res.keys(), {
            'invoice_state': 'invoiced',
            }, context=context)
        return res
stock_picking()

class account_report(osv.osv):
    _inherit="account.report.report"
    _columns={
        'type': fields.selection([
            ('bs', 'Balance Sheet'),
            ('pl', 'Income Statement'),
            ('cf', 'Cash Flow Statement'),
            ('indicator','Indicator'),
            ('view','View'),
            ('other','Others')],
            'Type', required=True),
    }
account_report()

# _inherit not implemented for osv_memory in 5.0, only in 5.2
import account

# set thai chart of accounts as default when configuring new db
def _default_chart(self,cr,uid,context):
    print "_defaut_chart"
    res=self.pool.get("ir.module.module").search(cr,uid,[("name","=","l10n_chart_th")])
    if not res:
        return None
    return res[0]
account.account.account_config_wizard._defaults["charts"]=_default_chart

# create journals from template differently than default account module
def action_create(self, cr, uid, ids, context=None):
    print "action_create",ids,context
    obj_multi = self.browse(cr,uid,ids[0])
    obj_acc = self.pool.get('account.account')
    obj_acc_tax = self.pool.get('account.tax')
    obj_journal = self.pool.get('account.journal')
    obj_sequence = self.pool.get('ir.sequence')
    obj_acc_template = self.pool.get('account.account.template')
    obj_fiscal_position_template = self.pool.get('account.fiscal.position.template')
    obj_fiscal_position = self.pool.get('account.fiscal.position')

    # Creating Account
    obj_acc_root = obj_multi.chart_template_id.account_root_id
    tax_code_root_id = obj_multi.chart_template_id.tax_code_root_id.id
    company_id = obj_multi.company_id.id

    #new code
    acc_template_ref = {}
    tax_template_ref = {}
    tax_code_template_ref = {}
    todo_dict = {}

    #create all the tax code
    children_tax_code_template = self.pool.get('account.tax.code.template').search(cr, uid, [('parent_id','child_of',[tax_code_root_id])], order='id')
    for tax_code_template in self.pool.get('account.tax.code.template').browse(cr, uid, children_tax_code_template):
        vals={
            'name': (tax_code_root_id == tax_code_template.id) and obj_multi.company_id.name or tax_code_template.name,
            'code': tax_code_template.code,
            'info': tax_code_template.info,
            'parent_id': tax_code_template.parent_id and ((tax_code_template.parent_id.id in tax_code_template_ref) and tax_code_template_ref[tax_code_template.parent_id.id]) or False,
            'company_id': company_id,
            'sign': tax_code_template.sign,
        }
        new_tax_code = self.pool.get('account.tax.code').create(cr,uid,vals)
        #recording the new tax code to do the mapping
        tax_code_template_ref[tax_code_template.id] = new_tax_code

    #create all the tax
    for tax in obj_multi.chart_template_id.tax_template_ids:
        #create it
        vals_tax = {
            'name':tax.name,
            'sequence': tax.sequence,
            'amount':tax.amount,
            'type':tax.type,
            'applicable_type': tax.applicable_type,
            'domain':tax.domain,
            'parent_id': tax.parent_id and ((tax.parent_id.id in tax_template_ref) and tax_template_ref[tax.parent_id.id]) or False,
            'child_depend': tax.child_depend,
            'python_compute': tax.python_compute,
            'python_compute_inv': tax.python_compute_inv,
            'python_applicable': tax.python_applicable,
            'is_wht':tax.is_wht,
            'base_code_id': tax.base_code_id and ((tax.base_code_id.id in tax_code_template_ref) and tax_code_template_ref[tax.base_code_id.id]) or False,
            'tax_code_id': tax.tax_code_id and ((tax.tax_code_id.id in tax_code_template_ref) and tax_code_template_ref[tax.tax_code_id.id]) or False,
            'base_sign': tax.base_sign,
            'tax_sign': tax.tax_sign,
            'ref_base_code_id': tax.ref_base_code_id and ((tax.ref_base_code_id.id in tax_code_template_ref) and tax_code_template_ref[tax.ref_base_code_id.id]) or False,
            'ref_tax_code_id': tax.ref_tax_code_id and ((tax.ref_tax_code_id.id in tax_code_template_ref) and tax_code_template_ref[tax.ref_tax_code_id.id]) or False,
            'ref_base_sign': tax.ref_base_sign,
            'ref_tax_sign': tax.ref_tax_sign,
            'include_base_amount': tax.include_base_amount,
            'description':tax.description,
            'company_id': company_id,
            'type_tax_use': tax.type_tax_use
        }
        new_tax = obj_acc_tax.create(cr,uid,vals_tax)
        #as the accounts have not been created yet, we have to wait before filling these fields
        todo_dict[new_tax] = {
            'account_collected_id': tax.account_collected_id and tax.account_collected_id.id or False,
            'account_paid_id': tax.account_paid_id and tax.account_paid_id.id or False,
        }
        tax_template_ref[tax.id] = new_tax

    #deactivate the parent_store functionnality on account_account for rapidity purpose
    self.pool._init = True

    children_acc_template = obj_acc_template.search(cr, uid, [('parent_id','child_of',[obj_acc_root.id])])
    children_acc_template.sort()
    for account_template in obj_acc_template.browse(cr, uid, children_acc_template):
        tax_ids = []
        for tax in account_template.tax_ids:
            tax_ids.append(tax_template_ref[tax.id])
        #create the account_account

        dig = obj_multi.code_digits
        code_main = account_template.code and len(account_template.code) or 0
        code_acc = account_template.code or ''
        if code_main>0 and code_main<=dig and account_template.type != 'view':
            code_acc=str(code_acc) + (str('0'*(dig-code_main)))
        vals={
            'name': (obj_acc_root.id == account_template.id) and obj_multi.company_id.name or account_template.name,
            #'sign': account_template.sign,
            'currency_id': account_template.currency_id and account_template.currency_id.id or False,
            'code': code_acc,
            'type': account_template.type,
            'user_type': account_template.user_type and account_template.user_type.id or False,
            'reconcile': account_template.reconcile,
            'shortcut': account_template.shortcut,
            'note': account_template.note,
            'parent_id': account_template.parent_id and ((account_template.parent_id.id in acc_template_ref) and acc_template_ref[account_template.parent_id.id]) or False,
            'tax_ids': [(6,0,tax_ids)],
            'company_id': company_id,
        }
        new_account = obj_acc.create(cr,uid,vals)
        acc_template_ref[account_template.id] = new_account
    #reactivate the parent_store functionnality on account_account
    self.pool._init = False
    self.pool.get('account.account')._parent_store_compute(cr)

    for key,value in todo_dict.items():
        if value['account_collected_id'] or value['account_paid_id']:
            obj_acc_tax.write(cr, uid, [key], vals={
                'account_collected_id': acc_template_ref[value['account_collected_id']],
                'account_paid_id': acc_template_ref[value['account_paid_id']],
            })

    # Creating Journals
    vals_journal={}
    view_id = self.pool.get('account.journal.view').search(cr,uid,[('name','=','Journal View')])[0]
    seq_id = obj_sequence.search(cr,uid,[('name','=','Account Journal')])[0]

    if obj_multi.seq_journal:
        seq_id_sale = obj_sequence.search(cr,uid,[('name','=','Sale Journal')])[0]
        seq_id_purchase = obj_sequence.search(cr,uid,[('name','=','Purchase Journal')])[0]
        seq_id_receipt = obj_sequence.search(cr,uid,[('name','=','Receipt Journal')])[0]
        seq_id_payment = obj_sequence.search(cr,uid,[('name','=','Payment Journal')])[0]
        seq_id_general = obj_sequence.search(cr,uid,[('name','=','General Journal')])[0]
    else:
        seq_id_sale = seq_id
        seq_id_purchase = seq_id
        seq_id_receipt = seq_id
        seq_id_payment = seq_id
        seq_id_general = seq_id

    vals_journal['view_id'] = view_id

    #Sales Journal
    vals_journal['name'] = _('Sales Journal')
    vals_journal['type'] = 'sale'
    vals_journal['code'] = _('SAJ')
    vals_journal['sequence_id'] = seq_id_sale

    if obj_multi.chart_template_id.property_account_receivable:
        vals_journal['default_credit_account_id'] = acc_template_ref[obj_multi.chart_template_id.property_account_income_categ.id]
        vals_journal['default_debit_account_id'] = acc_template_ref[obj_multi.chart_template_id.property_account_income_categ.id]

    obj_journal.create(cr,uid,vals_journal)

    # Purchase Journal
    vals_journal['name'] = _('Purchase Journal')
    vals_journal['type'] = 'purchase'
    vals_journal['code'] = _('EXJ')
    vals_journal['sequence_id'] = seq_id_purchase

    if obj_multi.chart_template_id.property_account_payable:
        vals_journal['default_credit_account_id'] = acc_template_ref[obj_multi.chart_template_id.property_account_expense_categ.id]
        vals_journal['default_debit_account_id'] = acc_template_ref[obj_multi.chart_template_id.property_account_expense_categ.id]

    obj_journal.create(cr,uid,vals_journal)

    # Receipt Journal
    vals_journal['name'] = _('Receipt Journal')
    vals_journal['type'] = 'receipt'
    vals_journal['code'] = _('RCJ')
    vals_journal['sequence_id'] = seq_id_receipt
    obj_journal.create(cr,uid,vals_journal)

    # Payment Journal
    vals_journal['name'] = _('Payment Journal')
    vals_journal['type'] = 'payment'
    vals_journal['code'] = _('PMJ')
    vals_journal['sequence_id'] = seq_id_payment
    obj_journal.create(cr,uid,vals_journal)

    # General Journal
    vals_journal['name'] = _('General Journal')
    vals_journal['type'] = 'general'
    vals_journal['code'] = _('GNJ')
    vals_journal['sequence_id'] = seq_id_general
    obj_journal.create(cr,uid,vals_journal)


    #create the properties
    property_obj = self.pool.get('ir.property')
    fields_obj = self.pool.get('ir.model.fields')

    todo_list = [
        ('property_account_receivable','res.partner','account.account'),
        ('property_account_payable','res.partner','account.account'),
        ('property_account_expense_categ','product.category','account.account'),
        ('property_account_income_categ','product.category','account.account'),
        ('property_account_expense','product.template','account.account'),
        ('property_account_income','product.template','account.account')
    ]
    for record in todo_list:
        r = []
        r = property_obj.search(cr, uid, [('name','=', record[0] ),('company_id','=',company_id)])
        account = getattr(obj_multi.chart_template_id, record[0])
        field = fields_obj.search(cr, uid, [('name','=',record[0]),('model','=',record[1]),('relation','=',record[2])])
        vals = {
            'name': record[0],
            'company_id': company_id,
            'fields_id': field[0],
            'value': account and 'account.account,'+str(acc_template_ref[account.id]) or False,
        }
        if r:
            #the property exist: modify it
            property_obj.write(cr, uid, r, vals)
        else:
            #create the property
            property_obj.create(cr, uid, vals)

    fp_ids = obj_fiscal_position_template.search(cr, uid,[('chart_template_id', '=', obj_multi.chart_template_id.id)])

    if fp_ids:
        for position in obj_fiscal_position_template.browse(cr, uid, fp_ids):

            vals_fp = {
                       'company_id' : company_id,
                       'name' : position.name,
                       }
            new_fp = obj_fiscal_position.create(cr, uid, vals_fp)

            obj_tax_fp = self.pool.get('account.fiscal.position.tax')
            obj_ac_fp = self.pool.get('account.fiscal.position.account')

            for tax in position.tax_ids:
                vals_tax = {
                            'tax_src_id' : tax_template_ref[tax.tax_src_id.id],
                            'tax_dest_id' : tax.tax_dest_id and tax_template_ref[tax.tax_dest_id.id] or False,
                            'position_id' : new_fp,
                            }
                obj_tax_fp.create(cr, uid, vals_tax)

            for acc in position.account_ids:
                vals_acc = {
                            'account_src_id' : acc_template_ref[acc.account_src_id.id],
                            'account_dest_id' : acc_template_ref[acc.account_dest_id.id],
                            'position_id' : new_fp,
                            }
                obj_ac_fp.create(cr, uid, vals_acc)

    return {
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'ir.actions.configuration.wizard',
            'type': 'ir.actions.act_window',
            'target':'new',
    }
account.account.wizard_multi_charts_accounts.action_create=action_create
