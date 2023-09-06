"""
This script analyzes .out files and monitors geometry and SCF convergence
"""

#####################
###Version Control###
#####################

# (since I will probably not convince the Carrow lab to use Github)
# Update this value whenever edits are made and add to the Edit History comment.

edit_history = """
Version Initials    Date            Summary
1.0     ARS         28-Jun-2023     initial draft
2.0     ARS         29-Jun-2023     added documentation and handles jobs that crashed during SCF
2.0                                 also reports last SCF
"""
version = edit_history.strip().split('\n')[-1].split()[0]


import csv
import sys


def write_convergence_csv(lines, name):
    """writes a csv containing SCF and Geopt convergence data"""

    def find_negative_frequencies(start, outlines):
        """This helper function retrieves negative frequencies once a hessian is found"""
        results = []
        i = start + 11
        while outlines[i].strip() != '':
            frequency = float(outlines[i].split()[1])
            if frequency < 0:
                results.append(frequency)
            i += 1
        return results

    def process_scf(lines, start):
        """This helper function finds the number of iterations an SCF step has taken
        by reading outlines starting from start.
        It returns the number of iterations, start, and the end of the scf section"""

        # finds the end of the SCF section. If the end string is not found, uses end of file
        end = None
        for i in range(start, len(lines)):
            if '*****************************************************' in lines[i]:
                end = i
                break
        if not end:
            end = len(lines)

        # scans from end to start of the SCF section looking for a line that starts with a digit
        for i in reversed(range(start, end)):
            splitline = lines[i].split()
            if len(splitline) > 0:
                iteration = splitline[0]
                if iteration.isdigit():
                    return int(iteration) + 1, start, end

    # initialize tables with headers
    # tolerance table skips rows to line up with convergence table
    geopt_tolerance_table = [['', '', '', '', 'Tolerances'],
                       ['', '', '', '', 'abs Energy Change', 'RMS Gradient', 'MAX Gradient', 'RMS Step', 'MAX Step']]
    geopt_convergence_table = [['Convergence Data'],
                         ['Iteration', 'SCF Steps', 'Energy', 'rel Energy Change',
                          'abs Energy Change', 'RMS Gradient', 'MAX Gradient', 'RMS Step', 'MAX Step']]
    neg_freq_table = [['Negative Frequencies'], ['Iteration', 'Negative Frequencies']]

    # initialize the start and stop of the most recent SCF section
    scf_start = None
    scf_end = None

    for i in range(0, len(lines)):
        if 'GEOMETRY OPTIMIZATION CYCLE' in lines[i]:
            geopt_convergence_table.append([lines[i].split()[4], '', '', '', '', '', ''])
        elif lines[i] == 'SCF ITERATIONS\n':
            geopt_convergence_table[-1][1], scf_start, scf_end = process_scf(lines, i)
        elif 'FINAL SINGLE POINT ENERGY' in lines[i]:
            geopt_convergence_table[-1][2] = lines[i].split()[4]
        elif '|Geometry convergence|' in lines[i]:
            if len(geopt_convergence_table) == 3:
                # First iteration does not have a change in energy, so skip convergence_table[-1][2]
                # appending 'RMS Gradient', 'MAX Gradient', 'RMS Step', 'MAX Step'
                geopt_convergence_table[-1][5:9] = [line.split()[2] for line in lines[i + 3:i + 7]]
            else:
                # appending 'abs Energy Change', 'RMS Gradient', 'MAX Gradient', 'RMS Step', 'MAX Step'
                rel_en, rms_grad, max_grad, rms_step, max_step = [line.split()[2] for line in lines[i + 3:i + 8]]
                geopt_convergence_table[-1][3] = rel_en
                geopt_convergence_table[-1][4] = abs(float(rel_en))
                geopt_convergence_table[-1][5:9] = rms_grad, max_grad, rms_step, max_step

            # populates tolerance_table with first iteration of |Geometry convergence| that is complete
            if len(geopt_convergence_table) == 4:
                geopt_tolerance_table.append(['', '', '', ''] + [line.split()[3] for line in lines[i + 3:i + 8]])
        elif 'Writing the Hessian file to the disk' in lines[i]:
            iteration = geopt_convergence_table[-1][0]
            neg_freqs = find_negative_frequencies(i, lines)
            neg_freq_table.append([iteration, neg_freqs])

    # extends scf section to include summary but avoids crashing if file ends during scf
    if scf_end + 1 < len(lines):
        scf_end += 1

    csv_file = name + "_postmortem.csv"
    with open(csv_file, 'w', newline='') as w:
        writer = csv.writer(w)
        writer.writerows(geopt_tolerance_table)
        writer.writerows(['\n'])
        writer.writerows(geopt_convergence_table)
        writer.writerows(['\n'])
        writer.writerows(neg_freq_table)
        writer.writerows(['\n'])

        writer.writerow(['last SCF data'])
        for line in lines[scf_start + 2:scf_end+3]:
            if line.strip().startswith('*'):
                writer.writerow([line.strip()])
            else:
                writer.writerow(line.split())

    print(f'postmortem analysis written to {csv_file}')

if __name__ == '__main__':
    if sys.argv[1] == '-v' or sys.argv[1] == '-version':
        print(f'orca_postmortem version {version}')
        sys.exit(0)

    filename = sys.argv[1]
    with open(filename, 'r') as r:
        out_lines = r.readlines()
    summary_file = filename.split('.')[0]
    write_convergence_csv(out_lines, summary_file)
