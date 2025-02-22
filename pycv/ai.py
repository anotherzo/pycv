import os
import json
import yaml
import logging
import instructor
from anthropic import Anthropic
from dotenv import load_dotenv
from typing import Iterable
from pydantic import BaseModel, Field
from .baseclasses import CarStory, Cvitem, JobDescription, Summary

load_dotenv()  # Load environment variables from .env file

class Ai:
    def __init__(self):
        self.model = "claude-3-5-sonnet-20240620"
        self.max_tokens = 4096
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        self.logger = logging.getLogger(self.__class__.__name__)

    def ask(self, prompt:str, respmodel):
        client = instructor.from_anthropic(Anthropic(), mode=instructor.Mode.ANTHROPIC_JSON)
        self.logger.info("Asking AI for help... ")
        res = client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                response_model=respmodel,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
            ],
        )
        self.logger.info("... answer received.")
        return res
    
    def get_json_for(self, arr: list) -> str:
        res = [item.model_dump() for item in arr]
        return json.dumps(res)

    def get_experience(self, jobs:list, carstories:list, descriptions:list, joblink:str) -> Iterable[Cvitem]:
        promptpath = os.path.join(os.path.dirname(__file__), 'cars-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    jobs=self.get_json_for(jobs),
                    cars=self.get_json_for(carstories),
                    job=joblink
        )
        selectedStories = self.ask(prompt, Iterable[CarStory])
        promptpath = os.path.join(os.path.dirname(__file__), 'refine-cars-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    cars=self.get_json_for(selectedStories),
                    descriptions=self.get_json_for(descriptions),
                    job=joblink
        )
        return self.ask(prompt, Iterable[Cvitem])

    def get_job_summaries(self, skills:list, statements:list, joblink:str) -> Iterable[JobDescription]:
        promptpath = os.path.join(os.path.dirname(__file__), 'jobdescription-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    jobs=self.get_json_for(skills),
                    statements=self.get_json_for(statements),
                    job=joblink
        )
        return self.ask(prompt, Iterable[JobDescription])

    def get_summary(self, skills:list, statements:list, joblink:str) -> Summary:
        promptpath = os.path.join(os.path.dirname(__file__), 'summary-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    skills=self.get_json_for(skills),
                    statements=self.get_json_for(statements),
                    job=joblink
        )
        return self.ask(prompt, Summary)



class StubAi:
    def get_experience(self, jobs:list, carstories:list, descriptions:list, joblink:str) -> Iterable[CarStory]:
        return [
            Cvitem(job=1, item="foo"),
            Cvitem(job=1, item="bar"),
            Cvitem(job=1, item="baz"),
            Cvitem(job=2, item="foo"),
            Cvitem(job=2, item="bar"),
            Cvitem(job=2, item="baz"),
        ]

    def get_summary(self, skills:list, statements:list, joblink:str) -> Iterable[JobDescription]:
        return Summary(summary="This is some example text.")

    def get_job_summaries(self, skills:list, statements:list, joblink:str) -> Iterable[JobDescription]:
        return [
                JobDescription(job=1, description="Something I've done"),
                JobDescription(job=2, description="Something else I've done"),
        ]

