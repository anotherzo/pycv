import os
import sys
import logging
import subprocess
import click
from pycv import PyCv

@click.command()
@click.option('--joblink', '-j', prompt='Link to the job ad', help='URL of the job advertisement')
@click.option('--name', '-n', prompt='Project name', help='Name for the output report')
@click.option('--compile/--no-compile', '-c/-nc', default=True, help='Compile the LaTeX output (default: True)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def main(joblink: str, name: str, compile: bool, verbose: bool):
    """Generate a customized CV based on a job posting."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize PyCv
    cv = PyCv(joblink, name)

    # Generate and save LaTeX
    cv.save_latex()

    if compile:
        subprocess.Popen(f'xelatex {name}.tex', shell=True)

if __name__ == "__main__":
    main()
