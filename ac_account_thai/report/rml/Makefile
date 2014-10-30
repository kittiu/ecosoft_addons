all: voucher.rml bill_issue.rml accounting_report.rml

bill_issue.rml: bill_issue.odt
	tiny_sxw2rml.py $< > $@

voucher.rml: voucher.odt
	tiny_sxw2rml.py $< > $@

accounting_report.rml: accounting_report.sxw
	tiny_sxw2rml.py $< > $@

clean:
	rm -f *.rml
