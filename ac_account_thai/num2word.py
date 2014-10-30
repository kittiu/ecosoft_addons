#!/usr/bin/python
# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2009  Almacom (Thailand) Ltd.
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

sym={
    "en": {
        "sep": " ",
        "0": "zero",
        "x": ["one","two","three","four","five" ,"six","seven","eight","nine"],
        "1x": ["ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen"],
        "x0": ["twenty","thirty","fourty","fifty","sixty","seventy","eighty","ninety"],
        "100": "hundred",
        "1K": "thousand",
        "1M": "million",
    },
    "th": {
        "sep": "",
        "0": "ศูนย์",
        "x": ["หนึ่ง","สอง","สาม","สี่","ห้า" ,"หก","เจ็ด","แปด","เก้า"],
        "x0": ["สิบ","ยี่สิบ","สามสิบ","สี่สิบ","ห้าสิบ","หกสิบ","เจ็ดสิบ","แปดสิบ","เก้าสิบ"],
        "x1": "เอ็ด",
        "100": "ร้อย",
        "1K": "พัน",
        "10K": "หมื่น",
        "100K": "แสน",
        "1M":"ล้าน",
    }
}

def num2word(n,l="en"):
    #TODO:Support Thai Stang 
    if n==0:
        return sym[l]["0"] + " "
    elif n<10:
        return sym[l]["x"][n-1]
    elif n<100:
        if l=="en":
            if n<20:
                return sym[l]["1x"][n-10]
            else:
                return sym[l]["x0"][n/10-2]+(n%10 and sym[l]["sep"]+num2word(n%10,l) or "")
        elif l=="th":
            return sym[l]["x0"][n/10-1]+(n%10 and (n%10==1 and sym[l]["x1"] or sym[l]["x"][n%10-1]) or "")
    elif n<1000:
        return sym[l]["x"][n/100-1]+sym[l]["sep"]+sym[l]["100"]+(n%100 and sym[l]["sep"]+num2word(n%100,l) or "")
    elif n<1000000:
        if l=="en":
            return num2word(n/1000,l)+sym[l]["sep"]+sym[l]["1K"]+(n%1000 and sym[l]["sep"]+num2word(n%1000,l) or "")
        elif l=="th":
            if n<10000:
                return sym[l]["x"][n/1000-1]+sym[l]["1K"]+(n%1000 and num2word(n%1000,l) or "")
            elif n<100000:
                return sym[l]["x"][n/10000-1]+sym[l]["10K"]+(n%1000 and num2word(n%10000,l) or "")
            else:
                return sym[l]["x"][n/100000-1]+sym[l]["100K"]+(n%10000 and num2word(n%100000,l) or "")
    elif n<1000000000:
        return num2word(n/1000000,l)+sym[l]["sep"]+sym[l]["1M"]+sym[l]["sep"]+(n%1000000 and num2word(n%1000000,l) or "")
    else:
        return "N/A"

def num2word_th(n,l="th"):
    base=0
    end=0
    number = n
    if type(n) == type(''):
        number=float(n)
    word = ''
    if type(number) in (type(0),type(0.0)):
        number = ('%.2f'%number).split('.')
        base = num2word(int(number[0]),l=l)
        print number
        if int(number[1])!=0:
            end = num2word(int(number[1]),l=l)
        if base==0 and end==0:
            word='ศุนย์บาทถ้วน'
        if base!=0 and end==0:
            word=base+'บาทถ้วน'
        if base!=0 and end!=0:
            word=base+' '+end+'สตางค์'
    return word

if __name__ == '__main__':
    import sys
    n=sys.stdin.readline()
    print num2word_th(n)
