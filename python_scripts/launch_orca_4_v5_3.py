"""
This script iteratively creates .inp files for multiple .xyz files which all use the same orca keywords

each .xyz file should be named with the format {molecule_name}_{charge}_{spin}.xyz
this script also supports .xyz files formatted as {molecule_name}_{charge}_{spin}_in.xyz
for positive charges, use either the number or p (e.g. 1, 2, p1, p2)
for negative charges, use m or n (e.g. m1, m2, n1, n2)

the orca keywords will either be taken from a set of default files found at {default_path}
or a local file specified as an argument.

the memory will either be estimated automatically based on the molecular structures of the subjobs
or specified as an argument

the job time will either be specified as an argument (recommended) or set to a default value

if the '-scan' or '-s' flag is used, an interactive scan session is launched.

if the '-batchscan' or '-bs' flag is used, an interactive scan where all the subjobs scan the same space is launched.

if the '-write' or '-w' flag is usued, the job is written but not launched.

While creating the .inp files, this script renames the .xyz files to {molecule_name}_{charge}_{spin}_in.xyz
if they do not already end in '_in.xyz'

Lastly, this script creates a batch SLURM job using the memory, job time, and parallelization data provided

This script takes up to three optional user-specified system arguments:
 the job time, the memory per core, a settings file
It also takes two optional flags: '-scan' or '-write' (also '-s' and '-w')
This script requires no particular order for its flags and arguments

The shell script which launches this script passes the user email (sys.argv[1])
as well as the path to the Carrow group bin (sys.argv[2]).
This script reads the working directory's name and uses it as a variable, along with the names of the .xyz files
"""

#####################
###Version Control###
#####################

# (since I will probably not convince the Carrow lab to use Github)
# Update this comment whenever edits are made.

edit_history = """
version Initials    Date            Summary
1.0     ARS         23-Jun-2023     First draft of entire codebase is written
2.0     ARS         25-Jun-2023     Restructured to create individual .inp files
2.0                                 and launch them all from a common .sh file
2.1     ARS         25-Jun-2023     Streamlined code and incorporated ChatGPT recommendations
2.2     ARS         25-Jun-2023     Further edits under the wise guidance of ChatGPT
2.3     ARS         26-Jun-2023     Moved constants to __main__ block per unquestionable tutelage of ChatGPT
2.4     ARS         27-Jun-2023     Debugged a few problems
3.0     ARS         20-Jul-2023     Added two optional arguments for memory and settings file. Made time optional.
3.0                                 Added a function for estimating memory cost. Changed way settings path is hard coded
3.1     ARS         26-Jul-2023     Added compatibility with _in.xyz files, added error handling for poorly formatted
3.1                                 .xyz files, reformatted subjobs as classes
4.0     ARS         27-Jul-2023     Added interactive scan function, expanded memory estimate function
4.1     ARS         01-Aug-2023     Modified scan, modified memory models, changed SLURM to alternate orca jobs
4.1                                 and copying files, added 'write' functionality
5.0     ARS         13-Aug-2023     Refactored code, cleaned summary messages, and standardized formatting. 
5.0                                 Performed concurrently with process_orca_4_v4_0.py
5.1     ARS         15-Aug-2023     Expanded scans to bond angles and dihedrals
5.2     ARS         15-Aug-2023     Added batch scan functionality
5.3     ARS         15-Aug-2023     if -bs, then requires choose_atoms to have the same number. duplicate arguments
5.3                                 now throw an error. User can override MAX_STEPS error in scans. User Specified
5.3                                 memory now has a special string in summarize(). summarize() retweaked.
"""
version = edit_history.strip().split('\n')[-1].split()[0]

import os
import sys
import re
import numpy as np


class Parent(object):
    """holds parameters of the parent job
    These are every parameter universal to every orca .inp file
    as well as those parameters needed for the SLURM file"""

    def __init__(self):

        # assigns global variable job_name to parent for clarity
        self.name = job_name

        self.time = None
        self.memory_per_core = None
        self.custom_memory = False
        self.settings_path = None
        self.scan = False
        self.batch_scan = False

        self.parse_args()

    @staticmethod
    def is_time(time_string):
        """checks that a string is a valid time string using regular expression magic"""
        pattern = r'^\d+(?::\d+)*$'
        return bool(re.match(pattern, time_string))

    @staticmethod
    def generate_std_error(error_message=''):
        """Standard error message and exit command"""
        if error_message:
            print(f'Error: {error_message}')
        print('Usage: launch_orca_4 [d:hh:mm:ss] [nM] [filename] [-scan] [-write]')
        print('Use "launch_orca_4 -help" for the manual')
        sys.exit(1)

    def parse_args(self):
        """parses command line arguments to determine job time, memory per core, settings path,
        and determine if the -scan or -write flags are used.
        I have elected not to use the argparse module as I wanted to contextually determine argument types
        Perhaps I will regret this someday"""

        for arg in arg_list:
            if ':' in arg:
                if self.time is None:
                    if self.is_time(arg):
                        self.time = arg
                    else:
                        self.generate_std_error(f'Error! {arg} contains a ":" but is not a valid time string!')
                else:
                    self.generate_std_error(f'Error! Two time arguments: {arg} and {self.time}')

            elif arg.endswith('M'):
                if self.memory_per_core is None:
                    if arg[:-1].isdigit():
                        self.memory_per_core = int(arg[:-1])
                        self.custom_memory = True
                    else:
                        self.generate_std_error(f"Error! {arg} ends with 'M' but isn't an integer number of megabytes!")
                else:
                    self.generate_std_error(f'Error! Two memory arguments: {arg} and {self.time}')

            elif os.path.exists(arg):
                if self.settings_path is None:
                    self.settings_path = arg
                else:
                    self.generate_std_error(f'Error! Two settings file arguments: {arg} and {self.time}')

            # note that '-s -bs' causes a batch scan, which while redundant, is probably what the user wanted.
            elif arg.lower() in ('-s', '-scan'):
                self.scan = True
            elif arg.lower() in ('-bs', '-batchscan'):
                self.scan = True
                self.batch_scan = True

            elif arg.lower() in ('-w', '-write'):
                # This is handled in the shell file
                print(f'Executing {__file__} in write mode')
            elif arg.lower() in ('-v', '-version'):
                print(f'launch_orca_4 version {version}')
                sys.exit(0)
            else:
                self.generate_std_error(f'Error: {arg} not recognized')


class Atom(object):
    """Holds atom data relevant to subjob properties.
    Initializes using the xyz_lines from a subjob file"""

    def __init__(self, xyz_lines, index):
        atom_info = xyz_lines[index + 2].split()
        self.index = index
        self.element = atom_info[0]
        self.x = float(atom_info[1])
        self.y = float(atom_info[2])
        self.z = float(atom_info[3])


class ScanData(object):
    """Holds all data unique to scan jobs
    uses two interactive sessions to determine parameters
    and always allows user to exit software by entering '0'"""

    def __init__(self, subjob, reference=None):
        name = subjob.name
        xyz_data = subjob.lines

        # part of interactive session, so verbose
        print(PAGE_BREAK)
        print(f'    Setting up subjob {name}')

        # loops until user correctly enters two atoms or exits with 0
        self.atom_list = self.choose_atoms(xyz_data, reference)
        # loops until user correctly enters start, end, step_size or exits with 0
        self.scan_start, self.scan_end, self.n_steps = self.define_scan(reference)

        self.scan_codeblock = self.format_scan_codeblock()
        self.scan_desc = self.format_scan_desc()
        print(f'    {self.scan_desc}')

    @staticmethod
    def choose_atoms(xyz_data, reference):
        """Interactively choose the atoms for use in the scan
        Returns an array of 2-4 atoms
        designed to loop indefinitely until valid input is entered
        at any time, '0' can be pressed to exit"""

        class AtomNumberError(Exception):
            """for handling number of atoms outside 2-4"""
            pass

        class AtomNumberMatchError(Exception):
            """for handling number of atoms that don't match reference"""
            pass

        def vector(a, b):
            return np.array([a.x - b.x, a.y - b.y, a.z - b.z])

        def find_distance(a1, a2):
            return np.linalg.norm(vector(a1, a2))

        def find_angle(a1, a2, a3):
            v1 = vector(a2, a1)
            v2 = vector(a2, a3)

            radians = np.arccos(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

            return np.degrees(radians)

        def find_dihedral(a1, a2, a3, a4):
            v1 = vector(a1, a2)
            v2 = vector(a2, a3)
            v3 = vector(a3, a4)

            v1xv2 = np.cross(v1, v2)
            v2xv3 = np.cross(v2, v3)
            radians = np.arccos(np.dot(v1xv2, v2xv3) / (np.linalg.norm(v1xv2) * np.linalg.norm(v2xv3)))

            return np.degrees(radians)

        while True:
            choice = input('    Please enter atom list as integers separated with spaces\n    > ')
            if choice == '0':
                sys.exit(0)
            else:
                try:
                    index_list = map(int, choice.split())
                    atom_list = [Atom(xyz_data, index) for index in index_list]

                    if reference:
                        if len(atom_list) != len(reference.atom_list):
                            raise AtomNumberMatchError

                    if len(atom_list) == 2:
                        a1, a2 = atom_list
                        scan_type = f'{a1.element}-{a2.element}'
                        scan_value = f'{find_distance(a1, a2):.2f} angstroms'

                    elif len(atom_list) == 3:
                        a1, a2, a3 = atom_list
                        scan_type = f'{a1.element}-{a2.element}-{a3.element}'
                        scan_value = f'{find_angle(a1, a2, a3):.1f} degrees'

                    elif len(atom_list) == 4:
                        a1, a2, a3, a4 = atom_list
                        scan_type = f'{a1.element}-{a2.element}-{a3.element}-{a4.element}'
                        scan_value = f'{find_dihedral(a1, a2, a3, a4):.1f} degrees'

                    else:
                        raise AtomNumberError

                    print(f"""
    You have selected a {scan_type} scan.
    These atoms are currently at {scan_value}.
    Is this correct? Enter 'y' for yes, 'n' for no, or '0' to exit.""")
                    choice = input('    > ')
                    if choice == '0':
                        sys.exit(0)
                    elif choice == 'y':
                        return atom_list

                except (ValueError, IndexError):
                    print('    Error: Invalid input. Try again or enter "0" to quit.')
                except AtomNumberError:
                    print('    Error: Number of atoms must be between 2 and 4. Try again or enter "0" to quit.')
                except AtomNumberMatchError:
                    print('    Error: Number of atoms must match first scan during batch scans')

    @staticmethod
    def define_scan(reference):
        """Interactively set up scan_start, scan_end, n_steps
        designed to loop indefinitely until valid input is entered
        at any time, '0' can be pressed to exit
        if a reference is passed, instead duplicates this reference"""

        if reference is None:
            MAX_STEPS = 30
            TOLERANCE = 1e-5

            while True:
                scan_info = input(
                    '\n    Please enter the start value, end value,'
                    'and step size as three numbers separated with spaces\n    > '
                )
                if scan_info == '0':
                    sys.exit(0)

                try:
                    scan_start, scan_end, step_size = map(float, scan_info.split())

                    # determines number of steps and throws an error if 0 or excessive
                    # scan_end is reevaluated in n_steps does not come out as an int
                    n_steps = 0
                    if scan_start == scan_end:
                        print('    Error: start distance and end distance cannot be the same')
                        continue
                    # calculate number of steps
                    n_steps = abs((scan_end - scan_start) / step_size) + 1

                    # handles floating point errors
                    if abs(n_steps - round(n_steps)) < TOLERANCE:
                        n_steps = round(n_steps)
                    # if difference is larger than tolerance, this is assumed to be because the user's
                    # scan_start, scan_end, and step_size did not have an integer number of steps.
                    else:
                        n_steps = np.ceil(n_steps)
                        scan_end = round(scan_start + n_steps * step_size, 3)

                    # checks for suspiciously long scans and asks for verification
                    if n_steps > MAX_STEPS:
                        choice = input(f"""
    Error: Excessive number of steps ( > {MAX_STEPS}) detected!
    Consider decreasing number of steps by increasing step size or decreasing the distance to be scanned.
    Enter 'y' to override, 'n' to try again, or '0' to quit
    >""")
                        if choice == '0':
                            sys.exit(0)
                        elif choice == 'y':
                            break
                        else:
                            continue
                    else:
                        break

                except ValueError:
                    print('    Error: Invalid formatting. Try again or enter "0" to quit.')

        else:
            scan_start = reference.scan_start
            scan_end = reference.scan_end
            n_steps = reference.n_steps

        return scan_start, scan_end, n_steps

    def format_scan_desc(self):
        """This function formats a description of the scan in plaintext"""

        atoms = [f'{atom.element}{atom.index}' for atom in self.atom_list]
        hyph_atoms = '-'.join(atoms)
        scan_desc = f'scanning {hyph_atoms} from {self.scan_start} to {self.scan_end} in {self.n_steps} steps'

        return scan_desc

    def format_scan_codeblock(self):
        """This function formats the codeblock found in the .inp file"""

        # atom_list already validated to be 2-4 items long
        if len(self.atom_list) == 2:
            s_type = 'B'
        elif len(self.atom_list) == 3:
            s_type = 'A'
        elif len(self.atom_list) == 4:
            s_type = 'D'

        indices = ' '.join([str(atom.index) for atom in self.atom_list])

        scan_codeblock = f'%geom scan {s_type} {indices} = {self.scan_start}, {self.scan_end}, {self.n_steps} end end\n'

        return scan_codeblock


class Subjob(object):
    """This object holds all of the attributes necessary for creating an orca .inp file
    which are specific to the subjob and not universal to the parent.
    I chose to determine name, charge, spin in a separate function so that subjobs are only initialized
    when those parameters are successfully assigned."""

    def __init__(self, file, name, charge, spin):
        self.file = file
        self.name = name
        self.charge = charge
        self.spin = spin

        with open(file, 'r') as f:
            self.lines = f.readlines()


def print_nx2(array):
    """this function takes an nx2 array and prints it with the left column right aligned"""

    if not all(isinstance(row, list) and len(row) == 2 for row in array):
        raise ValueError('Input must be a two-dimensional array (list of lists) with two columns.')

    # Calculate the maximum width for the left column
    left_col_width = max(len(str(item[0])) for item in array)

    # Print the array with left column right-aligned and right column left-aligned
    for row in array:
        print(f'{row[0]:>{left_col_width}} {row[1]}')


def print_table(table):
    # Calculate the maximum width for each column
    column_widths = [max(len(str(item)) for item in column) for column in zip(*table)]

    # Print the table with left-aligned columns
    for row in table:
        formatted_row = "  ".join("{:<{width}}".format(item, width=width) for item, width in zip(row, column_widths))
        print(formatted_row)


def launch_settings_menu():
    """Launches interactive menu for choosing a default settings file"""
    settings = sorted(os.listdir(default_path))

    print(f"""
Welcome to the interactive settings menu!
Default files can be found/edited at {default_path}
Please use a number key to choose a setting.""")

    settings_array = []
    for index, option in enumerate(settings, start=1):
        settings_array.append([index, option])
    settings_array.append([0, 'Exit Script'])
    print_table(settings_array)

    while True:
        try:
            choice = int(input(' > '))
            if choice == 0:
                sys.exit(0)
            elif 0 < choice <= len(settings):
                return os.path.join(default_path, settings[choice - 1])
            else:
                print('Error: Not a valid setting')
        except (ValueError, TypeError):
            print('Error: Not a valid setting')


def count_atoms(xyz_data):
    """reads lines from an xyz file and returns the number of atoms from each row of the periodic table.
    Atoms in rows 6 and 7 are both partitioned into n6"""

    atom_types = {
        'n1': ('H', 'He'),
        'n2': ('Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne'),
        'n3': ('Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar'),
        'n4': (
            'K', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr'),
        'n5': ('Rb', 'Sr', 'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn', 'Sb', 'Te', 'I', 'Xe')
    }

    n_atoms = [0, 0, 0, 0, 0, 0]

    for line in xyz_data[2:]:
        line = line.strip()
        # skips empty lines
        if not line:
            continue

        atom, *_ = line.split()

        # mind the off by one
        if atom in atom_types['n1']:
            n_atoms[0] += 1
        elif atom in atom_types['n2']:
            n_atoms[1] += 1
        elif atom in atom_types['n3']:
            n_atoms[2] += 1
        elif atom in atom_types['n4']:
            n_atoms[3] += 1
        elif atom in atom_types['n5']:
            n_atoms[4] += 1
        else:
            n_atoms[5] += 1

    return n_atoms


def read_settings(settings_lines):
    """reads settings file for n_cores and determines if hess is calculated"""

    n_cores = None
    hess = False

    for line in settings_lines:
        fline = line.strip().lower()

        # checks %pal codeblock for n_cores e.g. %pal nprocs 12 end
        if fline.startswith('%pal nprocs'):
            n_cores = int(fline.split()[2])
        # checks ! line for frequency calculations, which use a QM hessian
        elif fline.startswith('!'):
            if 'freq' in fline:
                hess = True
        # checks if a QM hessian is requested directly
        elif 'calc_hess true' in fline:
            hess = True

    return n_cores, hess


def estimate_memory(atom_count, hess):
    """takes a 6 item list which indicates the atom count from an xyz file
    then estimates the memory demands from this data in MB"""

    def model_mem_hess(data_subset):
        """model of the memory demand as a function of number of each atom type"""
        n1, n2, n3, n4, n5, n6 = data_subset
        return 0 * n1 + 100 * n2 + 100 * n3 + 100 * n4 + 100 * n5 + 100 * n6 + 100

    def model_mem_no_hess(data_subset):
        n1, n2, n3, n4, n5, n6 = data_subset
        return 1000

    if hess:
        memory_estimate = model_mem_hess(atom_count)
    else:
        memory_estimate = model_mem_no_hess(atom_count)

    return memory_estimate


def get_subjob_properties(filename):
    """Extracts subjob name, charge, and spin from the filename.
       Returns None if file is formatted improperly
       I chose not to make this a method of the subjob class so that subjobs could be validated before construction"""

    subjob_name = filename.rstrip('_in')

    try:
        parts = subjob_name.split('_')

        if parts[-2].startswith('m') or parts[-2].startswith('n'):
            charge = -int(parts[-2][1:])
        elif parts[-2].startswith('p'):
            charge = int(parts[-2][1:])
        else:
            charge = int(parts[-2])

        spin = int(parts[-1])

        return subjob_name, charge, spin

    except(IndexError, ValueError):
        print(f'Error: {filename} is not formatted correctly')
        print('Enter "1" to skip file. Enter "0" to terminate launch_orca_4')

        choice = ''
        while choice not in ['0', '1']:
            choice = input(' > ')

        if choice == '0':
            sys.exit(0)
        else:
            return None


def generate_orca_input(parent, subjob):
    """Generates Orca input files and renames xyz files.
    input_name is added as a property to the subjob object"""

    subjob.input_name = subjob.name + '.inp'
    with open(subjob.input_name, 'w') as inp_file:
        if parent.scan:
            inp_file.write('#' + subjob.scan_data.scan_desc + '\n')
        inp_file.writelines(parent.settings)
        inp_file.write(f'%maxcore {parent.memory_per_core}\n')
        if parent.scan:
            inp_file.write(subjob.scan_data.scan_codeblock)
        inp_file.write(f'* xyzfile {subjob.charge} {subjob.spin} {subjob.name}_in.xyz\n\n')
        inp_file.write(f'# This input file was created with {os.path.basename(__file__)}\n')

    if not subjob.file.name.endswith('_in.xyz'):
        os.rename(subjob.file.name, f'{subjob.name}_in.xyz')


def generate_slurm_script(parent, subjobs):
    """Generates the SLURM .sh script."""

    subjob_string = ''
    for subjob in subjobs:
        subjob_string += f'$ORCA {subjob.input_name} >> $SLURM_SUBMIT_DIR/{subjob.name}.out\n'
        # copies every file that is not a .tmp file after each subjob finishes to allow for partial completion
        subjob_string += 'find "." -type f ! -iname "*.tmp*" -exec cp -t $SLURM_SUBMIT_DIR/ {} \;\n'

    slurm = f"""#!/bin/bash
#SBATCH -J {parent.name}
#SBATCH -t {parent.time}
#SBATCH -N 1
#SBATCH --ntasks-per-node={parent.n_cores}
#SBATCH --mem {parent.total_memory}G
#SBATCH --mail-user={email}
#SBATCH --mail-type=all

# This shell file was created with {os.path.basename(__file__)}

# Unload all loaded modules and reset everything to the original state;
# then load ORCA binaries and set communication protocol
module purge
module use /project/carrow/downloads/apps/modules
module add orca

# Copy contents of the working directory to a temporary directory,
# launch the job, and copy results back to the working directory
cp * $TMPDIR/
cd $TMPDIR
ORCA=`which orca`
echo $ORCA

# Subjobs
{subjob_string}

cd $SLURM_SUBMIT_DIR
"""

    with open(f'{parent.name}.sh', 'w') as slurm_file:
        slurm_file.write(slurm)


def summarize(parent, subjobs):
    """summarizes the job parameters for the user"""

    # General job parameters
    print(PAGE_BREAK)
    print('JOB SUMMARY')
    memory_string = f'{parent.memory_per_core}MB'
    if parent.custom_memory:
        memory_string += ' based on user input'
    else:
        if parent.hess:
            memory_string += ' based on QM hessian'
        else:
            memory_string += ' based on no QM hessian'
    summary_table = [
        ['job name', parent.name],
        ['job time', parent.time],
        ['number of cores', parent.n_cores],
        ['memory per core', memory_string],
        ['total memory', f'{parent.total_memory}GB'],
        ['settings', parent.settings_path]
    ]
    print_table(summary_table)
    print(parent.settings[0][:-1])
    print(PAGE_BREAK)

    # Scan job summary
    if parent.scan:
        scan_summary_table = []
        for subjob in subjobs:
            scan_summary_table.append([subjob.name, subjob.scan_data.scan_desc])
        print('SCAN SUMMARY')
        print_table(scan_summary_table)
        print(PAGE_BREAK)


def main():
    parent = Parent()

    # default behavior for job time and settings path
    if parent.time is None:
        parent.time = DEFAULT_TIME
    if parent.settings_path is None:
        # selection menu of default orca settings
        parent.settings_path = launch_settings_menu()

    # loads settings and cleanly formats them
    with open(parent.settings_path, 'r') as file:
        parent.settings = file.readlines()
    if parent.settings[-1][-1] != '\n':
        parent.settings[-1] += '\n'

    # Deletes frequency calculations from scan jobs - occurs before read_settings() to get parent.hess = None for scans
    if parent.scan:
        for i in range(len(parent.settings)):
            if 'freq' in parent.settings[i]:
                parent.settings[i] = parent.settings[i].replace('freq', '')
                print('removing the keyword "freq" because this is a scan job')

    parent.n_cores, parent.hess = read_settings(parent.settings)
    if parent.n_cores is None:
        print('Error! Settings file must contain %pal NPROCS')
        exit(1)

    # initiates subjob objects for every valid .xyz file and exits if there are none
    subjobs = []
    for file in os.scandir('.'):
        if file.name.endswith('.xyz'):
            subjob_properties = get_subjob_properties(file.name[:-4])
            # get_subjob_properties returns None when formatted incorrectly and skipped by user
            if subjob_properties is None:
                continue
            else:
                subjob_name, subjob_charge, subjob_spin = subjob_properties
                subjobs.append(Subjob(file, subjob_name, subjob_charge, subjob_spin))
    if len(subjobs) == 0:
        print('There are no valid xyz files! Terminating the script.')
        sys.exit(1)

    # default memory behavior
    if parent.memory_per_core is None:
        parent.memory_per_core = 0
        for subjob in subjobs:
            memory_estimate = estimate_memory(count_atoms(subjob.lines), parent.hess)
            if memory_estimate > parent.memory_per_core:
                parent.memory_per_core = memory_estimate
    # Ensures SLURM total memory is the lowest integer number of GB that satisfy the memory needs
    parent.total_memory = int(np.ceil(parent.memory_per_core * parent.n_cores / 1000))
    if parent.total_memory > MAX_ALLOWED_MEM:
        print(f"""Error! excessive memory ({parent.total_memory}G) requested!
Lower memory below {MAX_ALLOWED_MEM}G by lowering %pal nprocs or
specifying a lower memory_per_core on as an argument (e.g. launch_orca_4 2000M)""")
        exit(1)

    # Interactive scan session
    if parent.scan:
        print(PAGE_BREAK)
        print("""    Welcome to the interactive scan application!
    This application allows you to set up batch scan jobs
    Please note that orca atom numbering starts at 0 and does not contain elemental symbols.
    This means that atom C1 in Maestro or Avogadro should be specified as 0 here""")

        # If batch scan, set up the first scan manually and use it as a reference for the others
        if parent.batch_scan:
            subjobs[0].scan_data = ScanData(subjobs[0])
            for subjob in subjobs[1:]:
                subjob.scan_data = ScanData(subjob, reference=subjobs[0].scan_data)

        # If not a batch scan, set up all manually
        else:
            for subjob in subjobs:
                subjob.scan_data = ScanData(subjob)

        print(PAGE_BREAK)

    # Generate Orca input files and rename xyz files
    for subjob in subjobs:
        generate_orca_input(parent, subjob)

    # Generate the SLURM .sh script
    generate_slurm_script(parent, subjobs)

    # Summarizes results
    summarize(parent, subjobs)


if __name__ == '__main__':
    arg_list = sys.argv[3:7]
    email = sys.argv[1]
    default_path = f'{sys.argv[2]}/python_scripts/orca_settings/'
    DEFAULT_TIME = '1:00:00'
    MAX_ALLOWED_MEM = 120
    PAGE_BREAK = '-' * 80
    job_name = os.path.basename(os.getcwd())
    main()
