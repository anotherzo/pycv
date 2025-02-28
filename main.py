import os
import sys
import logging
import subprocess
import click
from pycv import PyCv

@click.command()
@click.option('--joblink', '-j', prompt='Link to the job ad', help='URL of the job advertisement')
@click.option('--projectname', '-n', prompt='Project name', help='Name for the output report')
@click.option('--compile/--no-compile', '-c/-nc', default=True, help='Compile the LaTeX output (default: True)')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--datadir', '-d', default='data', help='Directory containing YAML data files (default: data)')
@click.option('--track-costs/--no-track-costs', default=True, help='Track API costs (default: True)')
def main(joblink: str, projectname: str, compile: bool, verbose: bool, datadir: str, track_costs: bool):
    """Generate a customized CV based on a job posting."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize PyCv with datadir and cost tracking option
    cv = PyCv(joblink, projectname, datadir, track_costs=track_costs)

    # Generate and save LaTeX
    cv.save_latex()

    if compile:
        logging.info(f"Compiling LaTeX files for {projectname}...")
        # Redirect output to DEVNULL to hide it
        subprocess.run(['xelatex', 'resume.' + projectname + '.tex'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
        subprocess.run(['xelatex', 'coverletter.' + projectname + '.tex'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
        logging.info("LaTeX compilation completed.")

if __name__ == "__main__":
    main()
