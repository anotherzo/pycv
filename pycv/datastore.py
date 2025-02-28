from pathlib import Path
from typing import List, Dict, Optional
import yaml
import json
from abc import ABC, abstractmethod
from .baseclasses import Education, Job, CarStory, SkillCategory, Language, Statement, Summary

class DataStore(ABC):
    @abstractmethod
    def load_data(self):
        pass

class YamlStore(DataStore):
    def __init__(self, datadir: str = 'data'):
        self.datadir = datadir
        self.summary = None
        self.education = []
        self.jobs = []
        self.skills = []
        self.carstories = []
        self.personaldata = []
        self.languages = []
        self.statements = []


    def load_yaml(self, file_path: str) -> Dict:
        """Load and parse a YAML file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def load_data(self):
        """Load all YAML files from the data directory"""
        data_path = Path(self.datadir)

        # Load summary
        if (data_path / "summary.yaml").exists():
            data = self.load_yaml(str(data_path / "summary.yaml"))
            self.summary = Summary(summary=data.get('summary', ''))

        # Load education
        if (data_path / "education.yaml").exists():
            edu_data = self.load_yaml(str(data_path / "education.yaml"))
            self.education = sorted(
                [Education(**entry) for entry in edu_data],
                key=lambda x: x.edu
            )

        # Load jobs
        if (data_path / "jobs.yaml").exists():
            job_data = self.load_yaml(str(data_path / "jobs.yaml"))
            self.jobs = sorted(
                [Job(**entry) for entry in job_data],
                key=lambda x: x.job
            )
        
        # Load skills
        if (data_path / "skills.yaml").exists():
            skill_data = self.load_yaml(str(data_path / "skills.yaml"))
            self.skills = sorted(
                    [SkillCategory(**entry) for entry in skill_data],
                    key=lambda x: x.category
            )
        
        # Load languages
        if (data_path / "languages.yaml").exists():
            lang_data = self.load_yaml(str(data_path / "languages.yaml"))
            self.languages = sorted(
                    [Language(**entry) for entry in lang_data],
                    key=lambda x: x.language
            )

        # Load carstories
        if (data_path / "carstories.yaml").exists():
            cars_data = self.load_yaml(str(data_path / "carstories.yaml"))
            self.carstories = sorted(
                [CarStory(**entry) for entry in cars_data],
                key=lambda x: x.job
            )
        
        # Load personal data
        if (data_path / "headers.yaml").exists():
            self.headers = self.load_yaml(str(data_path / "headers.yaml"))[0]

        # Load statements
        if (data_path / "statements.yaml").exists():
            statement_data = self.load_yaml(str(data_path / "statements.yaml"))
            self.statements = sorted(
                [Statement(**entry) for entry in statement_data],
                key=lambda x: x.job
            )

