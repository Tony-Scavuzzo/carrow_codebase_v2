""" 
This script processes orca 4.2.1 .out files and creates a .csv file summarizing the results.
For each .out file, the following are tallied:
[molecule name, command line, job type, freq?, cost, E, H, G, neg freq, geom converged?]
This script creates a single .csv file with every result.
It also creates a shell script for visualizing the negative frequencies

For scan jobs, this script also processes relaxscanact.dat files
and reformats the .allxyz files so that they can be opened by maestro.
For the scan data, [coordinate, abs energy (a.u.), rel energy (kcal/mol), step (kcal/mol), type]
are tabulated, where type is edge, min, or max

It also reads the directory name and uses it as a constant.
"""

#####################
###Version Control###
#####################

# (since I will probably not convince the Carrow lab to use Github)
# Update this value whenever edits are made and add to the Edit History comment.

edit_history = """
Version Initials    Date            Summary
1.0     ARS         25-Jun-2023     First draft of entire codebase is written
1.1     ARS         26-Jun-2023     Extensive formatting and coding condensed
1.2     ARS         26-Jun-2023     Incorporated ChatGPT recommendations
2.0     ARS         26-Jun-2023     Now creates a .sh file for visualizing negative frequencies
2.1     ARS         29-Jun-2023     added case sensitivity as an option to the find_in function, minor debugging,
2.1                                 cost is now properly in cpu*h instead of h
2.2     ARS         21-Jul-2023     neg_freq shell file now prevents very large jobs (excessive negative frequencies)
2.2                                 from being run on the head node.
3.0     ARS         31-Jul-2023     performs processing of scan jobs, skips outfiles with problems
4.0     ARS         29-Aug-2023     minor bugs addressed, no longer overwrites existing files, small reformatting performed
"""
version = edit_history.strip().split('\n')[-1].split()[0]


import os
import sys
import csv


def get_available_filename(filename):
    """This function was defined by ChatGPT
    This function takes a desired fileneame (e.g. filename.ext)
    checks if this filename is already in use
    and if it is, renames (e.g. filename_n.ext)
    where n is the first integer that maps to an unused filename"""

    base, ext = os.path.splitext(filename)
    n = 1
    new_filename = filename

    # Check if the initial filename exists
    while os.path.exists(new_filename):
        new_filename = f"{base}_{n}{ext}"
        n += 1

    return new_filename


def cut_section(inlines, start=None, start_shift=0, end=None, end_shift=0):
    """Slices a list of strings (inlines) based on start and end flags.
    The start flag is searched for from the bottom of the file.
    the end flag is searched for starting from the last start flag
    The start_shift and end_shift parameters allow shifting the slice inward or outward.
    if start or end are not found, then the function returns None"""

    if start:
        start_index = None
        # search inlines for 'start' in reverse direction
        for i in reversed(range(len(inlines))):
            if start in inlines[i]:
                start_index = i
                break
        if not start_index:
            return None
    else:
        start_index = 0

    if end:
        end_index = None
        # search inlines for first 'end' after last 'start'
        for i in range(start_index, len(inlines)):
            if end in inlines[i]:
                end_index = i
                break
        if not end_index:
            return None
    else:
        end_index = -1
    return inlines[start_index - start_shift: end_index + end_shift]


def find_in(lines, starts_with, direction='f', case=True):
    """Returns the first line in a set of lines (lines) that starts with a specified string (starts_with).
    By default, it searches in the forward direction, but setting direction='r' reverses the behavior.
    By default, is case sensitive, but can be set to case insensitive
    Returns None if the string is not found."""

    if case:
        if direction == 'f':
            for line in lines:
                if line.startswith(starts_with):
                    return line
        elif direction == 'r':
            for line in reversed(lines):
                if line.startswith(starts_with):
                    return line
    else:
        if direction == 'f':
            for line in lines:
                if line.lower().startswith(starts_with.lower()):
                    return line
        elif direction == 'r':
            for line in reversed(lines):
                if line.lower().startswith(starts_with.lower()):
                    return line


def extract_energy(lines, flag, index):
    """Extracts energy (E, H, or G) from lines using the specified flag and index.
    It searches in the reverse direction to get the most recent data."""

    energy_line = find_in(lines, flag, direction='r')
    if not energy_line:
        return None
    energy = energy_line.split()[index]
    return energy 


def neg_freq_file(neg_freq_info, job_name):
    """writes the .sh file for visualizing negative frequencies if there are any
    Will prevent running the file outside of sbatch if there are excessive negative frequencies"""
    
    MAX_LENGTH = 10

    orca_pltvib = ''
    for row in neg_freq_info:
        orca_pltvib += f'orca_pltvib {row[0]}.hess {row[1]}\n'

    if len(neg_freq_info) < MAX_LENGTH:
        shell_file = f"""#!/bin/bash
module purge
module use /project/carrow/downloads/apps/modules
module add orca

echo "There are {len(neg_freq_info)} negative frequencies.
Executing neg_freqs.sh"

{orca_pltvib}
#This shell file was created with {os.path.basename(__file__)} and extracted from {job_name}/'
"""
    else:
        shell_file = f"""#!/bin/bash
#SBATCH -J neg_freqs
#SBATCH -t 1:00:00
#SBATCH -N 1
#SBATCH --ntasks-per-node=1

#checks if job is running through SLURM
if [ -n "$SLURM_JOB_ID" ]; then

    module purge
    module use /project/carrow/downloads/apps/modules
    module add orca

{orca_pltvib}
else
    echo "Warning: Excessive negative frequencies ({len(neg_freq_info)}) detected. 
Please run this job through SLURM with sbatch neg_freqs.sh"
    exit 0
fi
        
#This shell file was created with {os.path.basename(__file__)} and extracted from {job_name}/'
"""
    
    return shell_file


def process_scan(scan_data):
    """parses through .relaxscanact.dat files and returns a table recording
    coordinate, abs energy, rel energy, step, and type, where type can be 'edge', 'min', 'max', or ''"""

    # opens file and formats as a table
    with open(scan_data, "r") as s:
        lines = [list(map(float, line.split())) for line in s]

    # determines rel energy, step, and type for each line
    # scan_min finds minimum energy in column 1
    scan_min = min(lines, key=lambda x: x[1])[1]
    for i in range(len(lines)):

        # relative energy in kcal/mol
        lines[i].append((lines[i][1] - scan_min) * 627.509)

        if i == 0:
            lines[i].extend(['', 'edge'])
        else:
            # step - this is skipped for 0th iteration because no step taken
            lines[i].append(lines[i][2] - lines[i-1][2])
            # identifies local maxes and mins for previoius index
            if i > 1:
                if lines[i][3] <= 0 < lines[i - 1][3]:
                    lines[i-1].append('max')
                elif lines[i][3] >= 0 > lines[i - 1][3]:
                    lines[i-1].append('min')
                else:
                    lines[i-1].append('')
                if i == len(lines) - 1:
                    lines[i].append('edge')

    return lines


def process_allxyz(file, scan_data):
    """modifies allxyz files to be maestro readable and contain helpful data from the scan results"""

    if file.endswith('.allxyz'):
        basename = file.split('.')[0]
        with open(file, 'r') as old_file:
            content = old_file.readlines()

        # manipulates file content
        # trivial increment of i to link logic to next section, as 0th entry has no >
        i = 0
        content[1] = f'{basename} {scan_data[i][0]} {scan_data[i][-1]}\n'
        i += 1
        for j in range(len(content)):
            if '>' in content[j]:
                content[j] = '\n'
                content[j + 2] = f'{basename} {scan_data[i][0]} {scan_data[i][-1]}\n'
                i += 1
            j += 1

        # writes the new file
        new_name = file.replace('.allxyz', '.all.xyz')
        with open(new_name, 'w') as new_file:
            new_file.writelines(content)
        os.remove(file)
    else:
        print(f'Error! {file} is not a .allxyz file! Skipping file.')


def process_out_files():
    """Processes Orca .out files in the current directory and creates a summary CSV file.
    Also creates a .sh file which will visualize the negative frequencies."""

    orca_outs = [entry.name for entry in os.scandir('.') if entry.name.endswith('.out')]
    
    # initializes results table
    script_info = [f'This table was compiled with {os.path.basename(__file__)} and extracted from {job_name}/']
    table_header = ['molecule name', 'command line', 'job type', 'freq?', 'cost (cpu*hr)', 'E (a.u.)',
                    'H (a.u.)', 'G (a.u.)', 'neg freq (cm^-1)', 'geom converged?']
    results_table = []
    neg_freq_info = []
    scan_data = []

    for filename in orca_outs:
        try:
            with open(filename, 'r') as file:
                inlines = file.readlines()

            # removes leading and trailing spaces
            inlines = [line.strip() + '\n' for line in inlines]

            # skips .out files with multiple jobs and slurm .out files
            multiple_jobs = any('$new_job' in line.lower() for line in inlines)
            if multiple_jobs:
                print(f'{filename} contains multiple jobs. Skipping this file.')
                continue
            if 'slurm' in filename:
                continue

            # slices inputs and removes the '|  #>'
            inputs = cut_section(inlines, start='INPUT FILE\n', start_shift=-3, end='****END OF INPUT****\n')
            for i in range(len(inputs)):
                inputs[i] = inputs[i][inputs[i].index('>') + 2:]

            # finds molecule_name, commands, ncores, freq
            molecule_name = filename.split('.')[0]
            commands = find_in(inputs, '!')[:-1].lower()
            ncores = find_in(inputs, '%pal nprocs', case=False).split()[2]
            freq = ('freq' in commands)

            # determines job type
            if find_in(inputs, '%geom scan', case=False):
                job_type = 'scan'
            elif 'opt' in commands:
                job_type = 'opt'
            elif 'optts' in commands:
                job_type = 'optTS'
            else:
                job_type = 'SP'

            # determines if job finished correctly and then slices results and timing accordingly
            if inlines[-2] == '****ORCA TERMINATED NORMALLY****\n':
                start, end = '****END OF INPUT****\n', '****ORCA TERMINATED NORMALLY****\n'
                results = cut_section(inlines, start=start, start_shift=-3, end=end)
                timing = inlines[-1].split()
                days, hours, mins, secs = map(float, (timing[3], timing[5], timing[7], timing[9]))
                cost = int(ncores) * (24*days + hours + mins/60 + secs/3600)
            else:
                results = cut_section(inlines, start='****END OF INPUT****\n', start_shift=-3)
                cost = 'N/A'

            if job_type == 'scan':
                # skips most data for scans in favor of detailed scan logs
                freq, E, H, G, neg_freqs, geom_converged = '', '', '', '', '', ''

                scan_file = f'{molecule_name}.relaxscanact.dat'
                if os.path.exists(scan_file):
                    file_data = process_scan(scan_file)

                    # manipulates corresponding .allxyz file
                    process_allxyz(f'{molecule_name}.allxyz', file_data)

                    # elaborates results table with scan data
                    scan_data.extend([[], [scan_file], ['coordinate', 'abs energy (a.u.)', 'rel energy (kcal/mol)',
                                                        'step (kcal/mol)', 'type']])
                    scan_data.extend(file_data)
                else:
                    scan_data += [[f'{scan_file} does not exist'], ['']]

            else:
                # finds E, and if freq == True, also H, G, and neg_freqs
                # in the event of a job that crashed on the first SCF, E will be None?
                E = extract_energy(results, 'FINAL SINGLE POINT ENERGY', -1)
                if freq:
                    # in the event of a crashed job, H and G will be None
                    H = extract_energy(results, 'Total enthalpy', -2)
                    G = extract_energy(results, 'Final Gibbs free energy', -2)

                    # in the event of a crashed job, frequencies will be None
                    start, end = 'Writing the Hessian file to the disk', 'NORMAL MODES'
                    frequencies = cut_section(results, start=start, start_shift=-11, end=end, end_shift=-3)

                    # neg freqs is initialized even if not frequencies because empty cells are desired behavior
                    neg_freqs = []
                    if frequencies:
                        for line in frequencies:
                            frequency = float(line.split()[1])
                            if frequency < 0:
                                neg_freqs.append(frequency)
                                neg_freq_info.append([molecule_name, line.split()[0][:-1]])
                else:
                    H, G, neg_freqs = '', '', ''

                # finds geom_converged if calculation is a type of optimization
                if job_type == 'opt' or job_type == 'optTS':
                    flag = '***        THE OPTIMIZATION HAS CONVERGED     ***'
                    geom_converged = any(flag in line for line in results)
                else:
                    geom_converged = ''

            results_table.append([molecule_name, commands, job_type, freq, cost, E, H, G, neg_freqs, geom_converged])

        except (FileNotFoundError, PermissionError, IOError, ValueError, IndexError, TypeError) as e:
            print(f'Error with {filename}: {e}; Skipping file.')
            results_table.append([f'Error with {filename}: {e}; Skipping file.'])

    # writes the .csv file with results
    available_filename = get_available_filename(f'{job_name}_summary.csv')
    with open(available_filename, 'w', newline='') as file1:
        writer = csv.writer(file1)
        writer.writerows([script_info, table_header] + results_table)
        writer.writerows(scan_data)
    print(f'Summary file {job_name}_summary.csv created.')
    
    # writes the .sh file for visualizing negative frequencies if there are any
    if neg_freq_info:
        if os.path.exists('neg_freqs.sh'):
            choice = input("""Potential Error: neg_freqs.sh already exists
Do you want to overwrite neg_freqs with new data?
Enter 'y' to overwrite, or press any other key to exit
 > """)
            if choice != 'y':
                sys.exit(0)

        shell_file = neg_freq_file(neg_freq_info, job_name)
        with open(f'neg_freqs.sh', 'w') as file2:
            file2.writelines(shell_file)


if __name__ == '__main__':
    if len(sys.argv) == 2:
        if sys.argv[1] == '-v' or sys.argv[1] == '-version':
            print(f'process_orca_4 version {version}')
            sys.exit(0)
    job_name = os.path.basename(os.getcwd())
    process_out_files()
