import os
import sys
import logging
import subprocess
from pycv import PyCv

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    joblink = input("Link to the job ad, please:\n")
    projectname = input("What is the name of this report?\n")
    # Initialize PyCv
    cv = PyCv(joblink, projectname)

    # Generate and save LaTeX
    cv.save_latex()

    subprocess.run(['xelatex', 'resume.' + projectname + '.tex'])
    subprocess.run(['xelatex', 'coverletter.' + projectname + '.tex'])

if __name__ == "__main__":
     main()
