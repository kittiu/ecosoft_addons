# -*- encoding: utf-8 -*-
import os
from osv import osv
import xmlrpclib
import cStringIO as StringIO

jy_serv=xmlrpclib.ServerProxy("http://localhost:9999/")

def safe_unicode(obj, *args):
    """ return the unicode representation of obj """
    try:
        return unicode(obj, *args)
    except UnicodeDecodeError:
        # obj is byte string
        ascii_text = str(obj).encode('string_escape')
        return unicode(ascii_text)

def safe_str(obj):
    """ return the byte string representation of obj """
    try:
        return str(obj)
    except UnicodeEncodeError:
        # obj is unicode
        return unicode(obj).encode('utf-8')

def decode_vals(vals): #need to format for str and unicode object-
    dc={}
    for k,v in vals.items():
        k,v = unicode(k),safe_unicode(v) # key and value must the same type str,str
        dc[k]=v
    return dc

def pdf_fill(orig_pdf,vals):
    vals=decode_vals(vals)
    orig_pdf_abs=os.path.join(os.getcwd(),orig_pdf)
    tmp=os.tempnam()
    print 'filling pdf',orig_pdf,vals
    jy_serv.pdf_fill(orig_pdf_abs,tmp,vals)
    pdf=file(tmp).read()
    os.unlink(tmp)
    return pdf

def pdf_merge(pdf1,pdf2):
    try:
        tmp1=os.tempnam()
        tmp2=os.tempnam()
        tmp3=os.tempnam()
        file(tmp1,"w").write(pdf1)
        file(tmp2,"w").write(pdf2)
        cmd="/usr/bin/pdftk %s %s cat output %s"%(tmp1,tmp2,tmp3)
        os.system(cmd)
        pdf3=file(tmp3).read()
        os.unlink(tmp1)
        os.unlink(tmp2)
        os.unlink(tmp3)
        return pdf3
    except:
        raise Exception("Failed to merge PDF files")
