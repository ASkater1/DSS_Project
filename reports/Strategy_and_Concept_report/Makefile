strategy: edit_teamdata.tex edit_summary.tex edit_businessdataunderstanding.tex 
	pdflatex strategy_team_???.tex
	bibtex strategy_team_???.aux
	pdflatex strategy_team_???.tex
	bibtex strategy_team_???.aux
	pdflatex strategy_team_???.tex

report: edit_teamdata.tex edit_summary.tex edit_businessdataunderstanding.tex edit_datapreparationmodelling.tex edit_evaluationdeployment.tex
	pdflatex report_team_???.tex
	bibtex report_team_???.aux
	pdflatex report_team_???.tex
	bibtex report_team_???.aux
	pdflatex report_team_???.tex
	
.PHONY: clean

all: 
	make strategy
	make report
	make clean



cleanall:
	-rm report_team_???.pdf
	-rm strategy_team_???.pdf
	make clean

clean:
	-rm report_team_???.aux report_team_???.log report_team_???.bbl report_team_???.blg report_team_???.out report_team_???.snm report_team_???.toc report_team_???.nav report_team_???.lot report_team_???.lof
	-rm strategy_team_???.aux strategy_team_???.log strategy_team_???.bbl strategy_team_???.blg strategy_team_???.out strategy_team_???.snm strategy_team_???.toc strategy_team_???.nav strategy_team_???.lot strategy_team_???.lof


