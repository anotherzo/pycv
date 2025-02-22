# CV Generator

A Python tool that generates a professional CV/resume in PDF format using LaTeX and the Awesome-CV template.

## Features

- Loads CV data from YAML files
- Takes a link to a job ad to fit your resume to the position you seek
- Uses Claude for content enhancement
- Generates a professional PDF using Jinja2 and LaTeX
- Based on the Awesome-CV template

## Requirements

- Python 3.13+
- uv (not required but strongly encouraged)
- LaTeX installation with XeLaTeX
- Fonts: Lora and Fira
- Some AI key comes in handy

## Installation

1. Clone this repository
2. Set up your API key:
   ```bash
   export ANTHROPIC_API_KEY='your-api-key'
   ```

## Usage

1. Update your CV data in the YAML files under `data/`:
   - `carstories.yaml`: CAR stories (challenge, action, result) with skills and a job identifier
   - `education.yaml`: Educational background
   - `jobs.yaml`: Work experience with job identifier
   - `skills.yaml`: Skills and competencies
   - `headers.yaml`: Various things like phone number, mail address...
   - `languages.yaml`: The languages you speak
   - `statements.yaml`: Statements about last job positions, with job identifiers

2. Generate your resume:
   ```bash
    uv run main.py
   ```

## Changing things

### Privacy
PyCv sends some parts of your data to an online LLM. This is restricted to:

- The link for the job ad
- CAR stories in `data/carstories.yaml`
- Jobs data in `data/jobs.yaml`
- Job Statements in `data/statements.yaml`
- Skills in `data/skills.yaml` 

When creating these data files, you might want to make sure you do not include any personal data, names of actual companies or other things you do not want to share with the internet.

***Not*** sent are information in `data/headers.yaml` such as your phone number or your email address.

### Using different AI models
PyCv uses  [`instructor`](https://python.useinstructor.com) in `ai.py`. If you want to address a different model (the code defaults to Claude), you will have to adapt `client = ...` and the parametrization of the model in the constructor and in `ask()`.

### Using different prompts and different output languages
All AI prompts are save in `pycv/*-prompt.txt`. Feel free to adapt those to your needs. The current version is in German; you might want to change that.

### Changing the layout of the PDF
All things layout are done in the jinja2 templates in the templates folder. If you want to simply test different layout options, you can run `main.py` with the project name `test`; this will simply exchange the AI parts with some default strings to test if the LaTeX part works as expected.

Entries in `data/headers` are transformed into header tags defined in `awesome-cv.cls`. The value for the key `phone` will be used as `\phone{value}` in the latex output. To add different/more/less header information, add the appropriate entries in `data/headers.yaml`.

## Data Structure

### Education (`education.yaml`)
```yaml
- edu: 1
  title: "Degree Title"
  organization: "Institution Name"
  location: "Location"
  date:
  - "Start"
  - "End"
  desc: "Optional description"
```

### Jobs (`jobs.yaml`)
```yaml
- job: 1
  position: "Job Title"
  organization: "Company Name"
  location: "Location"
  date:
    - "Start"
    - "End"
```

### Skills (`skills.yaml`)
```yaml
- Category:
  - "Skill 1"
  - "Skill 2"
```

### CAR stories (`carstories.yaml`)
```yaml
- job: 1
  challenge: "Something happened"
  action: "I did this"
  result: "This was the outcome"
  skills:
  - Skill 1
  - Skill 2
```

### Personal Information (`headers.yaml`)
```yaml
- photo: data/myface.jpg
  name:
  - MyFirstname
  - Lastname
  position: Something Great
  address: Where I live
  mobile: 123 45 67 890
  email: me@home.somewhere
  linkedin: findme-here-aswell
```

### Languages (`languages.yaml`)
```yaml
- language: Some Language
  level: Mostly fine
```

### Statements (`statements.yaml`)
```yaml
- job: 1
  statement: Mr Me was always...
```

## License

This project uses the Awesome-CV template which is licensed under CC BY-SA 4.0.
