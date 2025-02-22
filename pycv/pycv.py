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
from .ai import Ai, StubAi

class PyCv:
    def __init__(self, joblink: str, projectname: str, datadir: str = 'data'):
        """Initialize the PyCv class with OpenAI credentials"""
        self.datastore = YamlStore(datadir)
        self.datastore.load_data()
        self.joblink = joblink
        self.projectname = projectname
        self.ai = Ai()
        if self.projectname == "test":
            self.ai = StubAi()
        self.logger = logging.getLogger(self.__class__.__name__)

    def generate_latex(self):
        """Generate the complete LaTeX document"""
        self.logger.info("LaTeX-Generierung gestartet.") 
        latex_jinja_env = jinja2.Environment(
            block_start_string = r'\BLOCK{',
            block_end_string = '}',
            variable_start_string = r'\VAR{',
            variable_end_string = '}',
            comment_start_string = r'\#{',
            comment_end_string = '}',
            line_statement_prefix = '%%',
            line_comment_prefix = '%#',
            trim_blocks = True,
            autoescape = False,
            loader = jinja2.FileSystemLoader(os.path.abspath('./templates'))
        )
        template = latex_jinja_env.get_template('resume.tex.jinja')
        return template.render(
                headers = self.datastore.headers,
                name = self.datastore.headers['name'],
                summary = self.ai.get_summary(self.datastore.skills, self.datastore.statements, self.joblink),
                jobblocks = self._get_job_blocks(),
                education = self.datastore.education,
                skills = self.datastore.skills,
                languages = self.datastore.languages
        )

    def _get_job_blocks(self) -> list:
        jobblocks = []
        jobdescriptions = self.ai.get_job_summaries(self.datastore.jobs, self.datastore.statements, self.joblink)
        jobitems = self.ai.get_experience(self.datastore.jobs, self.datastore.carstories, jobdescriptions, self.joblink)
        for job in self.datastore.jobs:
            jds = [jd for jd in jobdescriptions if jd.job == job.job]
            jis = [ji for ji in jobitems if ji.job == job.job]
            jobblocks += [[job, jds, jis]]
        return jobblocks

    def save_latex(self):
        filename = self.projectname + ".tex"
        with open(filename, "w") as fout:
            fout.write(self.generate_latex())
