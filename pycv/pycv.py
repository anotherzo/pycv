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
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Always use StubAi for test mode
        if self.projectname == "test":
            self.ai = StubAi()
        else:
            # Try to initialize the AI, fall back to StubAi if there's an error
            try:
                self.ai = Ai()
            except Exception as e:
                self.logger.warning(f"Could not initialize AI service: {e}")
                self.logger.warning("Falling back to StubAi for testing purposes.")
                self.ai = StubAi()

    def _get_jinja_env(self):
        return jinja2.Environment(
            block_start_string = '\BLOCK{',
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

    def generate_coverletter(self):
        """Generate the complete LaTeX document"""
        self.logger.info("Started processing coverletter...") 
        latex_jinja_env = self._get_jinja_env()
        template = latex_jinja_env.get_template('coverletter.tex.jinja')
        
        # Try to get letterinfo, fall back to stub if it fails
        try:
            letterinfo = self.ai.get_letterinfo(
                        self.datastore.statements,
                        self.datastore.carstories,
                        self.joblink)
        except Exception as e:
            self.logger.warning(f"Error getting letterinfo from AI: {e}")
            self.logger.warning("Using stub letterinfo instead.")
            stub_ai = StubAi()
            letterinfo = stub_ai.get_letterinfo(
                        self.datastore.statements,
                        self.datastore.carstories,
                        self.joblink)
        
        latex_coverletter = template.render(
                headers = self.datastore.headers,
                letterinfo = letterinfo,
                name = self.datastore.headers['name'],
                joblink = self.joblink,
        )
        filename = "coverletter."  + self.projectname + ".tex"
        with open(filename, "w") as fout:
            fout.write(latex_coverletter)

    def generate_resume(self):
        """Generate the complete LaTeX document"""
        self.logger.info("Started processing resume...") 
        latex_jinja_env = self._get_jinja_env()
        template = latex_jinja_env.get_template('resume.tex.jinja')
        
        # Try to get summary, fall back to stub if it fails
        try:
            summary = self.ai.get_summary(self.datastore.skills, self.datastore.statements, self.joblink)
        except Exception as e:
            self.logger.warning(f"Error getting summary from AI: {e}")
            self.logger.warning("Using stub summary instead.")
            stub_ai = StubAi()
            summary = stub_ai.get_summary(self.datastore.skills, self.datastore.statements, self.joblink)
        
        latex_resume = template.render(
                headers = self.datastore.headers,
                name = self.datastore.headers['name'],
                summary = summary,
                jobblocks = self._get_job_blocks(),
                education = self.datastore.education,
                skills = self.datastore.skills,
                languages = self.datastore.languages,
                joblink = self.joblink,
        )
        filename = "resume."  + self.projectname + ".tex"
        with open(filename, "w") as fout:
            fout.write(latex_resume)

    def _get_job_blocks(self) -> list:
        jobblocks = []
        try:
            jobdescriptions = self.ai.get_job_summaries(self.datastore.jobs, self.datastore.statements, self.joblink)
            jobitems = self.ai.get_experience(self.datastore.jobs, self.datastore.carstories, jobdescriptions, self.joblink)
        except Exception as e:
            self.logger.warning(f"Error getting AI-generated content: {e}")
            self.logger.warning("Using stub data instead.")
            # Fall back to stub data
            stub_ai = StubAi()
            jobdescriptions = stub_ai.get_job_summaries(self.datastore.jobs, self.datastore.statements, self.joblink)
            jobitems = stub_ai.get_experience(self.datastore.jobs, self.datastore.carstories, jobdescriptions, self.joblink)
        
        for job in self.datastore.jobs:
            jds = [jd for jd in jobdescriptions if jd.job == job.job]
            jis = [ji for ji in jobitems if ji.job == job.job]
            jobblocks += [[job, jds, jis]]
        return jobblocks

    def save_latex(self):
        self.generate_resume()
        self.generate_coverletter()
