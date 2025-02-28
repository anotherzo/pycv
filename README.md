# CV Generator

A Python tool that generates a professional CV/resume in PDF format using LaTeX and the Awesome-CV template.

## Features

- Loads CV data from YAML files
- Takes a link to a job ad to fit your resume and coverletter to the position you seek
- No (all too) personal information is sent to the interwebs
- Uses Claude for content enhancement
- Generates professional PDFs using Jinja2 and LaTeX
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

### But this is all in German?
Yes, because that's what fits my needs. Feel free to change the template in `template/` or the prompts in `pycv/*-prompt.txt` to your own taste.

### Using different AI models
PyCv uses  [`instructor`](https://python.useinstructor.com) in `ai.py`. If you want to address a different model (the code defaults to Claude), you will have to adapt `client = ...` and the parametrization of the model in the constructor and in `ask()`.

### Using different prompts and different output languages
All AI prompts are save in `pycv/*-prompt.txt`. Feel free to adapt those to your needs. The current version is in German; you might want to change that.

### Changing the layout of the PDF
All things layout are done in the jinja2 templates in the templates folder. If you want to test different layout options, you can run `main.py` with the project name `test`; this will exchange the AI parts with some default strings to test if the LaTeX part works as expected.

Entries in `data/headers` are transformed into header tags defined in `awesome-cv.cls`. The value for the key `phone` will be used as `\phone{value}` in the latex output. To add different/more/less header information, add the appropriate entries in `data/headers.yaml`.

## Data Structure

### CAR stories (`carstories.yaml`)
(`job` links with identifier in `jobs.yaml`)
```yaml
- job: 1
  challenge: "Something happened"
  action: "I did this"
  result: "This was the outcome"
  skills:
  - Skill 1
  - Skill 2
- job: 2
  ...
```

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
- edu: 2
  ...
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
- job: 2
  ...
```

### Languages (`languages.yaml`)
```yaml
- language: Some Language
  level: Mostly fine
- language: Other Language
  ...
```

### Skills (`skills.yaml`)
```yaml
- category: Some Topic I Know About
  - "Skill 1"
  - "Skill 2"
- category:
  ...
```

### Statements (`statements.yaml`)
(`job` links with identifier in `jobs.yaml`)
```yaml
- job: 2
  statement: >
   Mr me was hired as a Super Contractor to fix the wrinkles in the fabric of spacetime in our lavatories. He...
- job: 1
  ...
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


### Statements (`statements.yaml`)
```yaml
- job: 1
  statement: Mr Me was always...
```

## License

This project uses the Awesome-CV template which is licensed under CC BY-SA 4.0.
