import os
import sys
import logging
import subprocess
import click
from pycv import PyCv

@click.command()
@click.option('--joblink', '-j', prompt='Link to the job ad', help='URL of the job advertisement. Can be a link to a local file.')
@click.option('--projectname', '-n', prompt='Project name', help='Name for the output report')
@click.option('--compile/--no-compile', '-c/-nc', default=True, help='Compile the LaTeX output (default: True)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--datadir', '-d', default='data', help='Directory containing YAML data files (default: data)')
def main(joblink: str, projectname: str, compile: bool, verbose: bool, datadir: str):
    """Generate a customized CV based on a job posting."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize PyCv with datadir
    cv = PyCv(joblink, projectname, datadir)

    # Generate and save LaTeX
    cv.save_latex()

    if compile:
        subprocess.run(['xelatex', 'resume.' + projectname + '.tex'])
        subprocess.run(['xelatex', 'coverletter.' + projectname + '.tex'])

if __name__ == "__main__":
    main()
