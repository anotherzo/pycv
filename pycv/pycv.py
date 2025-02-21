import os
import json
import yaml
import logging
import jinja2
from pathlib import Path
import instructor
from anthropic import Anthropic
from typing import List, Dict, Optional, Iterable
from pydantic import BaseModel, Field
from .datastore import YamlStore
from .baseclasses import CarStory, Cvitem, Language
from .ai import Ai

class PyCv:
    def __init__(self, joblink: str, projectname: str):
        """Initialize the PyCv class with OpenAI credentials"""
        self.datastore = YamlStore()
        self.datastore.load_data()
        self.joblink = joblink
        self.ai = Ai()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.projectname = projectname

    def _generate_header_information(self) -> str:
        """Generate the header information with personal details"""
        latex = []
        for key in self.datastore.headers:
            latex.append(self._genHeaderTag(key, self.datastore.headers[key]))
        return "\n".join(latex)

    def _genHeaderTag(self, tagname, dat) -> str:
        if dat.__class__.__name__ == 'str': 
            tag = ["\\" + tagname + "{" + dat + "}"]
        else:
            tag = ["\\" + tagname]
            for item in dat:
                tag.append("{" + item + "}")
        return "\n".join(tag)

    def _generate_education_section(self) -> str:
        """Generate the education section in LaTeX format"""
        latex = []
        latex.append("\\cvsection{Ausbildung}")
        latex.append("\\begin{cventries}")
        
        for edu in self.datastore.education:
            entry = [
                "\n\n\\cventry",
                "{" + edu.title + "}",  # position/title
                "{" + edu.organization + "}",  # organization
                "{" + edu.location + "}",  # location
                "{" + edu.timerange + "}",  # date range
                "{" + (edu.desc or '') + "}"  # description
            ]
            latex.append("".join(entry))
        
        latex.append("\\end{cventries}")
        return "\n".join(latex)

    def _generate_summary_section(self) -> str:
        """Generate the summary section in LaTeX format"""
        aisummary = self.ai.get_summary(self.datastore.skills, self.datastore.statements, self.joblink)
        latex = []
        latex.append("\\cvsection{Zusammenfassung}")
        latex.append("\\begin{cvparagraph}\n\n")
        latex.append("\\begin{multicols}{2}\n")
        latex.append(aisummary.summary)
        latex.append("\\end{multicols}\n")
        latex.append("\\end{cvparagraph}")
        return "\n".join(latex)

    def _generate_language_section(self) -> str:
        """Generate the language section in LaTeX format"""
        latex = []
        latex.append("\\cvsection{Sprachen}")
        latex.append("\\begin{cvskills}")
        for language in self.datastore.languages:
            entry = [
                "\\cvskill",
                "{" + language.language + "}\n",
                "{" + language.level + "}\n",
            ]
            latex.append("".join(entry))
        latex.append("\\end{cvskills}")
        return "\n".join(latex)


    def _generate_skills_section(self) -> str:
        """Generate the skills section in LaTeX format"""
        latex = []
        latex.append("\\cvsection{Technische Fähigkeiten}")
        latex.append("\\begin{cvskills}")
        
        for cat in self.datastore.skills:
            entry = [
                "\\cvskill",
                "{" + cat.category + "}\n",
                "{" + ", ".join(cat.items) + "}"
            ]
            latex.append("".join(entry))
        
        latex.append("\\end{cvskills}")
        return "\n".join(latex)

    def _generate_experience_section(self) -> str:
        """Generate the experience section in LaTeX format"""
        jobdescriptions = self.ai.get_job_summaries(self.datastore.jobs, self.datastore.statements, self.joblink)
        carstories = self.ai.get_experience(self.datastore.jobs, self.datastore.carstories, jobdescriptions, self.joblink)

        latex = []
        latex.append("\\cvsection{Berufserfahrung}")
        latex.append("\\begin{cventries}")

        for job in self.datastore.jobs:
            date_range = f"{job.date[0]}\\textemdash {job.date[1]}"
            jobstories = [story for story in carstories if story.job == job.job]
            jobdesc = [description for description in jobdescriptions if description.job == job.job]

            entry = [
                "\n\n\\cventry",
                "{" + job.position + "}",
                "{" + job.organization + "}",
                "{" + job.location + "}",
                "{" + date_range + "}",
            ]
            latex.append("\n".join(entry))
            if len(jobdesc) > 0:
                jobentry = [
                    "\\vspace{-0.2cm}",
                    jobdesc[0].description,
                    "\\vspace{.6cm}",
                ]
            else:
                jobentry = []
            if len(jobstories) > 0:
                stories = [
                    "\\begin{cvitems}",
                    self._format_jobstories(jobstories),
                    "\\end{cvitems}",
                ]
            else:
                stories = []
            
            content = jobentry + stories
            if len(content) > 0:
                content = ["{"] + content + ["}"]
                latex.append("\n".join(content))
            else:
                latex.append("{}")

        latex.append("\\end{cventries}")
        return "\n".join(latex)
    
    def _format_jobstories(self, stories: List[CarStory]) -> str:
        return "\n".join([self._format_jobstory(story) for story in stories])

    def _format_jobstory(self, story:CarStory) -> str:
        return "\\item {" + "{item}".format(
                item=self._latex_escape(story.item),
        ) + "}"

    def _latex_escape(self, str):
        # Replace a \ with $\backslash$
        # This is made more complicated because the dollars will be escaped
        # by the subsequent replacement. Easiest to add \backslash
        # now and then add the dollars
        # Must be done after escape of \ since this command adds latex escapes
        # Replace characters that can be escaped
        # Replace ^ characters with \^{} so that $^F works okay
        # Replace tilde (~) with \texttt{\~{}} # Replace tilde (~) with \texttt{\~{}}
        list = ["\\", "^", "~", '&', '%', '$', '#', '_', '{', '}']
        change_to = ["$\\backslash$", "\\^{}", "\\texttt{\\~{}}", '\\&', '\\%', '\\$', '\\#', '\\_', '\\{', '\\}']

        for i in list:
            if i in str:
                str = str.replace(i, change_to[list.index(i)])
                break
        return str

    def generate_latex(self):
        """Generate the complete LaTeX document"""
        self.logger.info("LaTeX-Generierung gestartet.") 
        latex_jinja_env = jinja2.Environment(
            block_start_string = '\BLOCK{',
            block_end_string = '}',
            variable_start_string = '\VAR{',
            variable_end_string = '}',
            comment_start_string = '\#{',
            comment_end_string = '}',
            line_statement_prefix = '%%',
            line_comment_prefix = '%#',
            trim_blocks = True,
            autoescape = False,
            loader = jinja2.FileSystemLoader(os.path.abspath('./templates'))
        )
        template = latex_jinja_env.get_template('resume.jinja.tex')
        return template.render(
                headers = self.generate_header_information(),
                fullname = self.datastore.headers['name'],
                summary = self.ai.get_summary(self.datastore.skills, self.datastore.statements, self.joblink),
                jobs = self.datastore.jobs,
                jobdescriptions = self.ai.get_job_summaries(self.datastore.jobs, self.datastore.statements, self.joblink),
                jobitems = self.ai.get_experience(self.datastore.jobs, self.datastore.carstories, jobdescriptions, self.joblink),
                education = self.datastore.education,
                skills = self.datastore.skills,
                languages = self.datastore.languages
        )

    def oldgenerate_latex(self) -> str:
        """Generate the complete LaTeX document"""
        self.logger.info("LaTeX-Generierung gestartet.") 
        sections = [
            "\\documentclass[11pt, a4paper]{awesome-cv}",
            "\\usepackage[ngerman]{babel}",
            "\\usepackage{multicol}",
            "\\geometry{left=2.5cm, top=2cm, right=2.5cm, bottom=2.5cm, footskip=1.5cm}",
            "\\definecolor{awesome}{HTML}{a57b5c}",
            "\\setbool{acvSectionColorHighlight}{true}",
            "\\renewcommand{\\acvHeaderSocialSep}{\\quad\\textbar\\quad}",
            self._generate_header_information(),
            "\\begin{document}",
            "\\makecvheader[C]",
            "\\makecvfooter{\\today}{" + " ".join(self.datastore.headers['name']) + "}{\\thepage}",
            self._generate_summary_section(),
            self._generate_experience_section(),
            self._generate_education_section(),
            self._generate_skills_section(),
            self._generate_language_section(),
            "\\end{document}"
        ]
        self.logger.info("LaTeX-Generierung beendet.")
        return "\n\n".join(sections)
    
    def save_latex(self):
        filename = self.projectname + ".tex"
        with open(filename, "w") as fout:
            fout.write(self.generate_latex())
