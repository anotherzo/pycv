import os
import json
import yaml
import logging
import instructor
from anthropic import Anthropic
from typing import Iterable
from pydantic import BaseModel, Field
from .baseclasses import CarStory, Cvitem, JobDescription, Summary, Letterinfo

class Ai:
    def __init__(self):
        self.model = "claude-3-5-sonnet-20240620"
        self.max_tokens = 4096
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
        self.logger.info("Getting job experience information...")
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
        self.logger.info("Getting job summaries...")
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
        self.logger.info("Getting resume summary...")
        promptpath = os.path.join(os.path.dirname(__file__), 'summary-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    skills=self.get_json_for(skills),
                    statements=self.get_json_for(statements),
                    job=joblink
        )
        return self.ask(prompt, Summary)

    def get_letterinfo(self, statements:list, carstories:list, joblink:str) -> Letterinfo:
        self.logger.info("Getting coverletter...")
        promptpath = os.path.join(os.path.dirname(__file__), 'letterinfo-prompt.txt')
        with open(promptpath, 'r') as f:
            prompt = f.read()
        prompt = prompt.format(
                    job=joblink,
                    statements=self.get_json_for(statements),
                    cars=self.get_json_for(carstories),
        )
        return self.ask(prompt, Letterinfo)


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

    def get_letterinfo(self, statements:list, carstories:list, joblink:str) -> Letterinfo:
        return Letterinfo(
                recipient=["ABC Company","Somestreet 42 Happytown"],
                subject="Application for the position of Head Of Everything",
                opening="Friends, romans, countrymen, lend me your ear",
                content="I really really want to get this thing",
        )
