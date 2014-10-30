#!/usr/bin/env jython

import sys
sys.path.append("/usr/share/java/itext.jar")

from java.io import FileOutputStream
from com.lowagie.text.pdf import PdfReader,PdfStamper,BaseFont
import re
import time
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer

def pdf_fill(orig_pdf,new_pdf,vals):
    print "pdf_fill",orig_pdf,new_pdf,vals
    t0=time.time()
    rd=PdfReader(orig_pdf)
    st=PdfStamper(rd,FileOutputStream(new_pdf))
    font=BaseFont.createFont("/usr/share/fonts/truetype/thai/Garuda.ttf",BaseFont.IDENTITY_H,BaseFont.EMBEDDED)
    form=st.getAcroFields()
    for k,v in vals.items():
        try:
            form.setFieldProperty(k,"textfont",font,None)
            form.setField(k,v.decode('utf-8'))
        except Exception,e:
            raise Exception("Field %s: %s"%(k,str(e)))
    st.setFormFlattening(True)
    st.close()
    t1=time.time()
    print "finished in %.2fs"%(t1-t0)
    return True

def pdf_merge(pdf1,pdf2):
    print "pdf_merge",orig_pdf,vals
    t0=time.time()
    pdf=pdf1
    t1=time.time()
    print "finished in %.2fs"%(t1-t0)
    return pdf

serv=SimpleXMLRPCServer(("localhost",9999))
serv.register_function(pdf_fill,"pdf_fill")
serv.register_function(pdf_merge,"pdf_merge")
print "waiting for requests..."
serv.serve_forever()
